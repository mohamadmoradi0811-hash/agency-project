import axios from 'axios';

// ایجاد نمونه اختصاصی برای APIها
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || '/api/v1',
  timeout: 10000,
});

// تنظیم Request Interceptor برای افزودن خودکار هدر X-Timezone
api.interceptors.request.use(
  (config) => {
    try {
      // استخراج منطقه زمانی محلی کاربر از مرورگر (مثلاً Asia/Tehran)
      const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      
      if (userTimezone) {
        config.headers['X-Timezone'] = userTimezone;
      }
    } catch (error) {
      console.error('Could not determine local timezone:', error);
      config.headers['X-Timezone'] = 'UTC';
    }

    // افزودن توکن احراز هویت در صورت وجود
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;