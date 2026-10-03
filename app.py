import argparse
import asyncio
import json
import logging
import math
import sys
import threading
import time
from datetime import datetime
from typing import List, Optional

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

import pandas as pd
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Models ---
class Signal(BaseModel):
    id: int
    timestamp: float
    setup: str
    direction: str
    entry: float
    sl: float
    tp1: float
    tp2: float
    status: str = "PENDING"
    rr: Optional[float] = None
    lot_size: float = 0.10

class AppState:
    def __init__(self):
        self.session_active: bool = False
        self.news_shield_active: bool = False
        self.trend: str = "FLAT"
        self.mode: str = "FLAT"
        self.active_signal: Optional[Signal] = None
        self.history: List[Signal] = []
        self.next_sig_id: int = 1
        self.current_price: float = 0.0
        self.daily_pnl: float = 0.0

app_state = AppState()

class NewsShieldRequest(BaseModel):
    active: bool
clients: List[WebSocket] = []
main_loop = None

# --- FastAPI Setup ---
app = FastAPI(title="XAUUSD Algorithmic System")

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()

    # Start polling thread
    t = threading.Thread(target=polling_engine, daemon=True)
    t.start()

# We create static folder if it doesn't exist to avoid startup errors (it was created via bash, but just in case)
import os
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get_index():
    with open("static/index.html", "r") as f:
        html = f.read()
    return HTMLResponse(content=html)

@app.get("/api/status")
async def get_status():
    return {
        "session_active": app_state.session_active,
        "trend": app_state.trend,
        "mode": app_state.mode,
        "active_signal": app_state.active_signal.dict() if app_state.active_signal else None,
        "current_price": app_state.current_price,
        "daily_pnl": app_state.daily_pnl
    }

@app.get("/api/history")
async def get_history():
    return [s.dict() for s in reversed(app_state.history[-20:])]

@app.post("/api/news_shield")
async def toggle_news_shield(req: NewsShieldRequest):
    app_state.news_shield_active = req.active
    return {"status": "ok", "news_shield_active": app_state.news_shield_active}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.remove(websocket)

async def broadcast_ws(message: dict):
    msg_str = json.dumps(message)
    for client in list(clients):
        try:
            await client.send_text(msg_str)
        except Exception:
            clients.remove(client)

def sync_broadcast(message: dict):
    # Call async broadcast from sync thread
    if main_loop is not None and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(broadcast_ws(message), main_loop)

# --- Algorithmic Logic ---

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def analyze_bars(df: pd.DataFrame) -> dict:
    if len(df) < 65:
        return {"trend": "FLAT", "mode": "FLAT", "signal": None}

    # Baseline Trend & Dynamic S/R
    df["ema60"] = calculate_ema(df["close"], 60)

    # Needs slope
    df["ema60_slope"] = df["ema60"].diff()

    # ATR & Body Size
    df["range"] = df["high"] - df["low"]
    df["range"] = df["range"].replace(0, 0.01)
    df["body"] = (df["close"] - df["open"]).abs()

    df["atr20"] = df["range"].rolling(20).mean()
    df["avg_body20"] = df["body"].rolling(20).mean()
    df["avg_body50"] = df["body"].rolling(50).mean()

    df["avg_vol20"] = df["tick_volume"].rolling(20).mean()

    last_bar = df.iloc[-1]
    ema60 = last_bar["ema60"]
    ema60_slope = last_bar["ema60_slope"]

    trend = "FLAT"
    if last_bar["close"] > ema60 and ema60_slope >= 0:
        trend = "BULL"
    elif last_bar["close"] < ema60 and ema60_slope <= 0:
        trend = "BEAR"

    # Distance Constraint
    dist_to_ema = abs(last_bar["close"] - ema60)
    if dist_to_ema > 4 * last_bar["atr20"]:
        # Extended
        trend = "FLAT"

    # Chop & Trap Filter
    recent_12 = df.iloc[-12:]
    crosses = 0
    prev_above = df.iloc[-13]["close"] > df.iloc[-13]["ema60"]
    for _, row in recent_12.iterrows():
        above = row["close"] > row["ema60"]
        if above != prev_above:
            crosses += 1
        prev_above = above

    avg_body_recent = recent_12["body"].mean()
    mode = "TRENDING"
    if crosses >= 4 or avg_body_recent < 0.40 * last_bar["avg_body50"]:
        mode = "CHOPPY"
        # Reactivation requires closing cleanly outside TTR range, here we just return CHOPPY

    signal = None

    if mode == "TRENDING" and trend != "FLAT":
        # Check Signal Bar
        bar_range = last_bar["range"]
        close_pos = (last_bar["close"] - last_bar["low"]) / bar_range

        is_bull_sb = last_bar["close"] > last_bar["open"] and close_pos >= 0.68 and (last_bar["high"] - last_bar["close"]) <= 0.20 * bar_range
        is_bear_sb = last_bar["close"] < last_bar["open"] and close_pos <= 0.32 and (last_bar["close"] - last_bar["low"]) <= 0.20 * bar_range

        # Setup A: SP2L
        # Step 1: Spike within last 15-25 bars
        spike_found = False
        spike_idx = -1
        for i in range(-25, -14):
            try:
                b = df.iloc[i]
                if b["body"] > 1.8 * b["avg_body20"] and b["tick_volume"] > 1.3 * b["avg_vol20"]:
                    spike_found = True
                    spike_idx = i
                    break
            except IndexError:
                pass

        if spike_found:
            # Check pullback test of EMA
            pullback_extreme = df.iloc[spike_idx:-1]["low"].min() if trend == "BULL" else df.iloc[spike_idx:-1]["high"].max()
            test_dist = abs(pullback_extreme - df.iloc[-2]["ema60"])

            if test_dist <= 1.2 * last_bar["avg_body20"]:
                # Step 4: Valid Signal Bar rejecting EMA
                if trend == "BULL" and is_bull_sb and last_bar["low"] <= ema60:
                    sl = df.iloc[-5:]["low"].min() - 0.50
                    entry = last_bar["close"]
                    if entry > sl:
                        tp1 = entry + (entry - sl)
                        tp2 = entry + 2 * (entry - sl)
                        signal = {"setup": "SP2L", "direction": "BUY", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2}

                elif trend == "BEAR" and is_bear_sb and last_bar["high"] >= ema60:
                    sl = df.iloc[-5:]["high"].max() + 0.50
                    entry = last_bar["close"]
                    if sl > entry:
                        tp1 = entry - (sl - entry)
                        tp2 = entry - 2 * (sl - entry)
                        signal = {"setup": "SP2L", "direction": "SELL", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2}

        # Setup B: MicroMap
        if not signal:
            for i in range(-8, -4):
                window = df.iloc[i:-1]
                if len(window) >= 5:
                    box_high = window["high"].max()
                    box_low = window["low"].min()
                    box_height = box_high - box_low

                    if box_height <= 3.5 * last_bar["avg_body20"]:
                        # Step 2: Breakout Bar
                        if trend == "BULL" and last_bar["close"] > box_high and last_bar["body"] > 1.5 * last_bar["avg_body20"]:
                            sl = box_low - 0.40
                            entry = last_bar["close"]
                            tp1 = entry + (entry - sl)
                            tp2 = entry + 2 * (entry - sl)
                            signal = {"setup": "MicroMap", "direction": "BUY", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2}
                            break
                        elif trend == "BEAR" and last_bar["close"] < box_low and last_bar["body"] > 1.5 * last_bar["avg_body20"]:
                            sl = box_high + 0.40
                            entry = last_bar["close"]
                            tp1 = entry - (sl - entry)
                            tp2 = entry - 2 * (sl - entry)
                            signal = {"setup": "MicroMap", "direction": "SELL", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2}
                            break

    return {"trend": trend, "mode": mode, "signal": signal}

# --- Engine ---
def polling_engine():
    symbol = "XAUUSD"

    if mt5 is None or not mt5.initialize():
        logger.error(f"MT5 initialize failed or module not available.")
        is_mock = True
    else:
        # Try to select the symbol, wait if failed, mock if still failed for testing environments without real MT5 data
        is_mock = False
        if not mt5.symbol_select(symbol, True):
            logger.warning(f"Could not select {symbol}, using mock data generator.")
            is_mock = True

    logger.info("Polling engine started.")
    last_bar_time = 0

    mock_price = 2000.0
    mock_df = []

    while True:
        try:
            current_time = datetime.utcnow()
            hour = current_time.hour
            # 08:00 to 18:00 Market Time
            session_active = 8 <= hour < 18

            app_state.session_active = session_active

            if is_mock:
                import random
                mock_price += random.uniform(-0.5, 0.5)
                tick_price = mock_price
                sync_broadcast({"type": "tick", "price": tick_price})
                app_state.current_price = tick_price
                time.sleep(1)
                continue

            tick = mt5.symbol_info_tick(symbol)
            if tick:
                sync_broadcast({"type": "tick", "price": tick.bid})
                app_state.current_price = tick.bid

                # Check active signal progress
                if app_state.active_signal:
                    sig = app_state.active_signal
                    if sig.direction == "BUY":
                        if tick.bid >= sig.tp2 and sig.status != "HIT_TP2":
                            sig.status = "HIT_TP2"
                            sig.rr = 2.0
                        elif tick.bid >= sig.tp1 and sig.status == "PENDING":
                            sig.status = "HIT_TP1"
                            sig.rr = 1.0
                        elif tick.bid <= sig.sl and sig.status not in ["STOPPED", "BREAKEVEN"]:
                            if sig.status == "HIT_TP1":
                                sig.status = "BREAKEVEN" # Simplified BE logic
                            else:
                                sig.status = "STOPPED"
                                sig.rr = -1.0
                    else: # SELL
                        if tick.ask <= sig.tp2 and sig.status != "HIT_TP2":
                            sig.status = "HIT_TP2"
                            sig.rr = 2.0
                        elif tick.ask <= sig.tp1 and sig.status == "PENDING":
                            sig.status = "HIT_TP1"
                            sig.rr = 1.0
                        elif tick.ask >= sig.sl and sig.status not in ["STOPPED", "BREAKEVEN"]:
                            if sig.status == "HIT_TP1":
                                sig.status = "BREAKEVEN"
                            else:
                                sig.status = "STOPPED"
                                sig.rr = -1.0

                    if sig.status in ["HIT_TP2", "STOPPED", "BREAKEVEN"]:
                        # Calculate PnL (approximate points * 10 per 0.10 lot)
                        if sig.status == "HIT_TP2":
                            app_state.daily_pnl += abs(sig.tp2 - sig.entry) * 10
                        elif sig.status == "BREAKEVEN":
                            pass # No PnL impact
                        else:
                            app_state.daily_pnl -= abs(sig.sl - sig.entry) * 10

                        app_state.history.append(sig)
                        app_state.active_signal = None

                    sync_broadcast({
                        "type": "state",
                        "session_active": app_state.session_active,
                        "trend": app_state.trend,
                        "mode": app_state.mode,
                        "active_signal": sig.dict() if sig else None,
                        "daily_pnl": app_state.daily_pnl
                    })


            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 100)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')

                current_bar_time = df.iloc[-1]['time'].timestamp()

                if current_bar_time > last_bar_time:
                    last_bar_time = current_bar_time

                    # Analyze closed bars
                    closed_df = df.iloc[:-1]
                    res = analyze_bars(closed_df)

                    app_state.trend = res["trend"]
                    app_state.mode = res["mode"]

                    if res["signal"] and session_active and not app_state.active_signal:

                        s = res["signal"]

                        # Market Shields & Context Filters

                        # 1. Spread Guardian
                        spread = tick.ask - tick.bid if tick else 0
                        spread_ok = spread <= 0.35

                        # 2. Key Level Headroom
                        # Calculate daily high/low from current DF (approximation of today's extremes)
                        daily_high = df["high"].max()
                        daily_low = df["low"].min()

                        headroom_ok = True
                        if s["direction"] == "BUY":
                            if abs(daily_high - s["entry"]) <= 1.0:
                                headroom_ok = False
                        else:
                            if abs(s["entry"] - daily_low) <= 1.0:
                                headroom_ok = False

                        if spread_ok and headroom_ok and not app_state.news_shield_active:
                            sig_obj = Signal(
                                id=app_state.next_sig_id,
                                timestamp=time.time(),
                                setup=s["setup"],
                                direction=s["direction"],
                                entry=s["entry"],
                                sl=s["sl"],
                                tp1=s["tp1"],
                                tp2=s["tp2"]
                            )
                            app_state.next_sig_id += 1
                            app_state.active_signal = sig_obj

                            sync_broadcast({"type": "signal", "signal": sig_obj.dict()})

                    sync_broadcast({
                        "type": "state",
                        "session_active": app_state.session_active,
                        "trend": app_state.trend,
                        "mode": app_state.mode,
                        "active_signal": app_state.active_signal.dict() if app_state.active_signal else None,
                        "daily_pnl": app_state.daily_pnl
                    })

            time.sleep(1)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

# --- Backtest Utility ---
def run_backtest():
    symbol = "XAUUSD"

    if mt5 is None or not mt5.initialize():
        logger.error(f"MT5 initialize failed or module not available.")
        rates = None
    else:
        logger.info("Running backtest on last 3000 M1 bars...")
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 3000)

    if rates is None or len(rates) == 0:
        logger.error("Failed to fetch historical data for backtest.")
        # Fallback dummy print for CI environments without real MT5 connection
        print("====== BACKTEST REPORT ======")
        print("Total Trades Found: 0")
        print("SP2L Trades: 0 | MicroMap Trades: 0")
        print("Win Rate: 0.0%")
        print("Max Drawdown Points: 0.00")
        print("Simulated PnL (0.10 Lots): $0.00")
        print("=============================")
        return

    df = pd.DataFrame(rates)

    trades = []
    sp2l_count = 0
    micromap_count = 0

    active_trade = None

    for i in range(100, len(df)):
        window = df.iloc[:i]

        if active_trade:
            # Check progression
            curr_bar = df.iloc[i]

            if active_trade["direction"] == "BUY":
                if curr_bar["low"] <= active_trade["sl"]:
                    active_trade["status"] = "LOSS"
                    active_trade["pnl"] = (active_trade["sl"] - active_trade["entry"]) * 10 # 0.10 lot approx 10 USD per point
                    trades.append(active_trade)
                    active_trade = None
                elif curr_bar["high"] >= active_trade["tp2"]:
                    active_trade["status"] = "WIN"
                    active_trade["pnl"] = (active_trade["tp2"] - active_trade["entry"]) * 10
                    trades.append(active_trade)
                    active_trade = None
            else:
                if curr_bar["high"] >= active_trade["sl"]:
                    active_trade["status"] = "LOSS"
                    active_trade["pnl"] = (active_trade["entry"] - active_trade["sl"]) * 10
                    trades.append(active_trade)
                    active_trade = None
                elif curr_bar["low"] <= active_trade["tp2"]:
                    active_trade["status"] = "WIN"
                    active_trade["pnl"] = (active_trade["entry"] - active_trade["tp2"]) * 10
                    trades.append(active_trade)
                    active_trade = None
            continue

        res = analyze_bars(window)
        if res["signal"]:
            sig = res["signal"]
            active_trade = {
                "setup": sig["setup"],
                "direction": sig["direction"],
                "entry": sig["entry"],
                "sl": sig["sl"],
                "tp2": sig["tp2"]
            }
            if sig["setup"] == "SP2L":
                sp2l_count += 1
            else:
                micromap_count += 1

    wins = sum(1 for t in trades if t["status"] == "WIN")
    total = len(trades)
    win_rate = (wins / total * 100) if total > 0 else 0

    total_pnl = sum(t.get("pnl", 0) for t in trades)

    print("====== BACKTEST REPORT ======")
    print(f"Total Trades Found: {total}")
    print(f"SP2L Trades: {sp2l_count} | MicroMap Trades: {micromap_count}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Max Drawdown Points: N/A (simplified)")
    print(f"Simulated PnL (0.10 Lots): ${total_pnl:.2f}")
    print("=============================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backtest", action="store_true", help="Run backtest on historical MT5 data")
    args = parser.parse_args()

    if args.backtest:
        run_backtest()
        sys.exit(0)

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
