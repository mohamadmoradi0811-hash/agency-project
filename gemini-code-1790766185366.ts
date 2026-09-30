'use client';

import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import api from '@/lib/axios';

// تعریف اسکیما با Zod
const leadSchema = z.object({
  serviceType: z.enum(['web', 'app', 'seo'], { required_error: 'لطفاً یک خدمت را انتخاب کنید' }),
  subCategory: z.string().optional(),
  hasDomainOrHost: z.string().optional(),
  platform: z.string().optional(),
  hasUiUx: z.string().optional(),
  currentSiteUrl: z.string().optional(),
  seoGoal: z.string().optional(),
  budget: z.string().min(1, 'انتخاب بودجه الزامی است'),
  timeline: z.string().min(1, 'تعیین ددلاین الزامی است'),
  fullName: z.string().min(2, 'نام و نام خانوادگی الزامی است'),
  phone: z.string().regex(/^09[0-9]{9}$/, 'شماره موبایل معتبر نیست (مثلاً 09123456789)'),
  email: z.string().email('ایمیل معتبر نیست').optional().or(z.literal('')),
});

type LeadFormData = z.infer<typeof leadSchema>;

export default function LeadFormController() {
  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<LeadFormData>({
    resolver: zodResolver(leadSchema),
    defaultValues: { serviceType: 'web' },
  });

  const selectedService = watch('serviceType');

  const onSubmit = async (data: LeadFormData) => {
    setIsSubmitting(true);
    setErrorMessage('');
    try {
      await api.post('/leads', data);
      setIsSuccess(true);
    } catch (error: any) {
      setErrorMessage(error?.response?.data?.message || 'خطایی در ثبت اطلاعات رخ داد. لطفاً دوباره تلاش کنید.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="max-w-2xl mx-auto bg-white rounded-2xl shadow-xl border border-gray-100 p-8 text-center">
        <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">✓</div>
        <h3 className="text-2xl font-bold text-gray-900 mb-2">درخواست شما با موفقیت ثبت شد!</h3>
        <p className="text-gray-600">کارشناسان ما در کمتر از ۲۴ ساعت آینده با شما تماس خواهند گرفت.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto bg-white rounded-2xl shadow-xl border border-gray-100 p-8">
      {/* نوار پیشرفت */}
      <div className="w-full bg-gray-200 h-2 rounded-full mb-8 overflow-hidden">
        <div className="bg-indigo-600 h-full transition-all duration-300" style={{ width: `${(step / 4) * 100}%` }}></div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)}>
        {/* مرحله ۱: انتخاب خدمت */}
        {step === 1 && (
          <div className="space-y-6">
            <h3 className="text-xl font-bold text-gray-900">به چه خدمتی نیاز دارید؟</h3>
            <div className="grid grid-cols-1 gap-4">
              {[
                { id: 'web', title: 'طراحی سایت', desc: 'سایت شرکتی، فروشگاهی یا پلتفرم اختصاصی' },
                { id: 'app', title: 'توسعه اپلیکیشن', desc: 'موبایل اپ (iOS/Android) و PWA' },
                { id: 'seo', title: 'سئو و دیجیتال مارکتینگ', desc: 'بهینه‌سازی رتبه و افزایش ترافیک ارگانیک' },
              ].map((item) => (
                <div
                  key={item.id}
                  onClick={() => setValue('serviceType', item.id as any)}
                  className={`cursor-pointer border-2 rounded-xl p-4 transition-all ${selectedService === item.id ? 'border-indigo-600 bg-indigo-50/50' : 'border-gray-200 hover:border-gray-300'}`}
                >
                  <h4 className="font-semibold text-gray-900">{item.title}</h4>
                  <p className="text-sm text-gray-500">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* مرحله ۲: شاخه‌های شرطی بر اساس خدمت انتخابی */}
        {step === 2 && (
          <div className="space-y-6">
            <h3 className="text-xl font-bold text-gray-900">جزئیات تخصصی پروژه</h3>
            {selectedService === 'web' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">نوع سایت</label>
                  <select {...register('subCategory')} className="w-full border border-gray-300 rounded-lg p-3">
                    <option value="store">فروشگاهی</option>
                    <option value="corporate">شرکتی</option>
                    <option value="custom">سفارشی / استارتاپی</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">آیا دامنه و هاست دارید؟</label>
                  <input {...register('hasDomainOrHost')} placeholder="مثلاً بله، هاست دانلود و دامنه ir داریم" className="w-full border border-gray-300 rounded-lg p-3" />
                </div>
              </div>
            )}
            {selectedService === 'app' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">پلتفرم هدف</label>
                  <input {...register('platform')} placeholder="iOS, Android, PWA" className="w-full border border-gray-300 rounded-lg p-3" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">آیا دیزاین UI/UX آماده دارید؟</label>
                  <input {...register('hasUiUx')} placeholder="خیر، نیاز به طراحی دارم" className="w-full border border-gray-300 rounded-lg p-3" />
                </div>
              </div>
            )}
            {selectedService === 'seo' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">آدرس سایت فعلی</label>
                  <input {...register('currentSiteUrl')} placeholder="https://example.com" className="w-full border border-gray-300 rounded-lg p-3" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">هدف اصلی سئو</label>
                  <input {...register('seoGoal')} placeholder="افزایش فروش / افزایش ترافیک" className="w-full border border-gray-300 rounded-lg p-3" />
                </div>
              </div>
            )}
          </div>
        )}

        {/* مرحله ۳: بودجه و زمان‌بندی */}
        {step === 3 && (
          <div className="space-y-6">
            <h3 className="text-xl font-bold text-gray-900">بودجه و ددلاین</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">محدوده بودجه تخمینی</label>
              <input {...register('budget')} placeholder="مثلاً بین ۵۰ تا ۱۰۰ میلیون تومان" className="w-full border border-gray-300 rounded-lg p-3" />
              {errors.budget && <p className="text-red-500 text-sm mt-1">{errors.budget.message}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">ددلاین مورد انتظار</label>
              <input {...register('timeline')} placeholder="مثلاً ۲ ماه آینده" className="w-full border border-gray-300 rounded-lg p-3" />
              {errors.timeline && <p className="text-red-500 text-sm mt-1">{errors.timeline.message}</p>}
            </div>
          </div>
        )}

        {/* مرحله ۴: اطلاعات تماس */}
        {step === 4 && (
          <div className="space-y-6">
            <h3 className="text-xl font-bold text-gray-900">اطلاعات تماس</h3>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">نام و نام خانوادگی</label>
              <input {...register('fullName')} className="w-full border border-gray-300 rounded-lg p-3" />
              {errors.fullName && <p className="text-red-500 text-sm mt-1">{errors.fullName.message}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">شماره تماس (موبایل)</label>
              <input {...register('phone')} placeholder="09123456789" className="w-full border border-gray-300 rounded-lg p-3" />
              {errors.phone && <p className="text-red-500 text-sm mt-1">{errors.phone.message}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">ایمیل (اختیاری)</label>
              <input {...register('email')} type="email" className="w-full border border-gray-300 rounded-lg p-3" />
              {errors.email && <p className="text-red-500 text-sm mt-1">{errors.email.message}</p>}
            </div>
            {errorMessage && <p className="text-red-600 text-sm">{errorMessage}</p>}
          </div>
        )}

        {/* دکمه‌های کنترل مراحل */}
        <div className="flex justify-between mt-8 pt-4 border-t border-gray-100">
          {step > 1 ? (
            <button type="button" onClick={() => setStep(step - 1)} className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
              بازگشت
            </button>
          ) : <div></div>}

          {step < 4 ? (
            <button type="button" onClick={() => setStep(step + 1)} className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700">
              مرحله بعد
            </button>
          ) : (
            <button type="submit" disabled={isSubmitting} className="px-6 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-50">
              {isSubmitting ? 'در حال ارسال...' : 'ثبت درخواست 🚀'}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}