'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { GoogleLogin } from '@react-oauth/google';
import { Database, Lock, Mail, ArrowRight } from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const { token, isLoading, login, loginWithGoogle } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isLoading && token) {
      router.replace('/');
    }
  }, [isLoading, token, router]);

  if (isLoading || token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-[#0B0F19] text-xs font-semibold text-slate-500">
        Đang chuyển hướng đến workspace...
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Vui lòng nhập đầy đủ email và mật khẩu');
      return;
    }
    setLoading(true);
    try {
      await login(email, password);
      router.push('/');
    } catch (err: any) {
      setError(err?.message || 'Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="glass-card rounded-2xl p-8 border border-indigo-500/20 shadow-2xl relative overflow-hidden bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
          <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-2xl -mr-10 -mt-10 pointer-events-none" />

          {/* Title */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-600/20 border border-indigo-200 dark:border-indigo-500/30 text-indigo-600 dark:text-indigo-400 mb-3 shadow-inner">
              <Database className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Đăng nhập Hệ thống</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              AI Semantic Layer Agent — Quản trị chỉ số nghiệp vụ
            </p>
          </div>

          {error && (
            <div className="mb-6 p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/30 text-red-600 dark:text-red-400 rounded-xl text-xs text-center font-medium">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1.5">
                Email
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-900/90 border border-slate-300 dark:border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-slate-400 dark:placeholder:text-slate-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-1.5">
                Mật khẩu
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                <input
                  type="password"
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-50 dark:bg-slate-900/90 border border-slate-300 dark:border-slate-700/80 rounded-xl pl-10 pr-4 py-2.5 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-slate-400 dark:placeholder:text-slate-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="gradient-btn w-full py-2.5 text-sm font-semibold text-white rounded-xl shadow-lg flex items-center justify-center gap-2 mt-2 cursor-pointer"
            >
              {loading ? 'Đang xử lý...' : 'Đăng nhập'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200 dark:border-slate-800" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white dark:bg-slate-900 px-3 text-slate-500 font-medium">Hoặc</span>
            </div>
          </div>

          {/* Google Authentication */}
          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={async (credentialResponse) => {
                if (credentialResponse.credential) {
                  try {
                    setError('');
                    await loginWithGoogle(credentialResponse.credential);
                    router.push('/');
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : 'Đăng nhập Google thất bại');
                  }
                }
              }}
              onError={() => {
                setError('Google OAuth chưa được cấu hình Client ID chính thức trong .env.local');
              }}
              theme="filled_black"
              shape="pill"
              text="signin_with"
            />
          </div>

          {/* Footer note */}
          <div className="mt-8 pt-4 border-t border-slate-200 dark:border-slate-800/80 text-center">
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Chưa có tài khoản?{' '}
              <Link href="/register" className="text-indigo-600 dark:text-indigo-400 hover:underline font-semibold">
                Tạo tài khoản mới
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
