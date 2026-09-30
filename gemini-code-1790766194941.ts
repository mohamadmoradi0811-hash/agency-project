'use client';

import React from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar } from 'recharts';

const revenueData = [
  { name: 'فروردین', revenue: 120 },
  { name: 'اردیبهشت', revenue: 180 },
  { name: 'خرداد', revenue: 250 },
  { name: 'تیر', revenue: 310 },
  { name: 'مرداد', revenue: 290 },
  { name: 'شهریور', revenue: 420 },
];

const funnelData = [
  { stage: 'بازدید لندینگ', count: 5000 },
  { stage: 'ثبت بریف', count: 1200 },
  { stage: 'تماس مشاور', count: 450 },
  { stage: 'قرارداد بسته شده', count: 120 },
];

export default function ExecutiveDashboard() {
  return (
    <div className="p-8 bg-gray-50 min-h-screen space-y-8">
      <h1 className="text-3xl font-bold tracking-tight text-gray-900">داشبورد مدیریتی پیشرفته</h1>

      {/* ۱. کارت‌های KPI */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { title: 'درآمد کل ماهانه', value: '۴۲۰ میلیون تومان', change: '+۱۸٪', color: 'text-emerald-600' },
          { title: 'لیدهای جدید امروز', value: '۲۴ درخواست', change: '+۵٪', color: 'text-indigo-600' },
          { title: 'نرخ تبدیل نهایی', value: '۱۰.۲٪', change: '+۲.۱٪', color: 'text-emerald-600' },
          { title: 'فاکتورهای معوق', value: '۳۵ میلیون تومان', change: '-۴٪', color: 'text-red-500' },
        ].map((kpi, idx) => (
          <div key={idx} className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
            <p className="text-sm text-gray-500 mb-1">{kpi.title}</p>
            <h3 className="text-2xl font-bold text-gray-900 mb-2">{kpi.value}</h3>
            <span className={`text-sm font-semibold ${kpi.color}`}>{kpi.change} نسبت به ماه گذشته</span>
          </div>
        ))}
      </div>

      {/* ۲. نمودارهای بصری */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* نمودار درآمد */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
          <h3 className="text-lg font-bold text-gray-900 mb-6">روند درآمد و جریان نقدینگی (میلیون تومان)</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={revenueData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" stroke="#6b7280" />
                <YAxis stroke="#6b7280" />
                <Tooltip />
                <Line type="monotone" dataKey="revenue" stroke="#4f46e5" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* نمودار قیفی تبدیل لیدها */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
          <h3 className="text-lg font-bold text-gray-900 mb-6">قیف نرخ تبدیل کاربران</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={funnelData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" stroke="#6b7280" />
                <YAxis dataKey="stage" type="category" stroke="#6b7280" width={110} />
                <Tooltip />
                <Bar dataKey="count" fill="#10b981" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}