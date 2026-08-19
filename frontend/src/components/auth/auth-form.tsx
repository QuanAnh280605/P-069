"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import { GoogleLogin } from '@react-oauth/google';
import { ArrowRight, Eye, EyeOff, Lock, LockKeyhole, Mail, Sparkles, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AnimatedSphere } from '@/components/landing/animated-sphere';

type AuthMode = 'login' | 'register';

export function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const { token, isLoading, login, register, loginWithGoogle } = useAuth();
  const isRegister = mode === 'register';

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isLoading && token) {
      router.replace('/workspace');
    }
  }, [isLoading, token, router]);

  if (isLoading || token) {
    return (
      <div className="h-screen flex items-center justify-center bg-background text-xs font-semibold text-muted-foreground">
        Đang chuyển hướng đến workspace...
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (isRegister) {
      if (!name || !email || !password) {
        setError('Vui lòng nhập đầy đủ thông tin');
        return;
      }
      if (password !== confirmPassword) {
        setError('Mật khẩu xác nhận không khớp');
        return;
      }
    } else {
      if (!email || !password) {
        setError('Vui lòng nhập đầy đủ email và mật khẩu');
        return;
      }
    }

    setLoading(true);
    try {
      if (isRegister) {
        await register(name, email, password);
      } else {
        await login(email, password);
      }
      router.push('/workspace');
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : isRegister
            ? 'Đăng ký thất bại. Vui lòng thử lại.'
            : 'Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page h-screen max-h-screen overflow-hidden bg-background text-foreground lg:grid lg:grid-cols-[0.92fr_1.08fr]">
      {/* Visual Panel */}
      <section className="auth-visual relative z-10 hidden h-full max-h-screen overflow-hidden border-r border-foreground/10 bg-foreground p-8 lg:p-10 text-background lg:flex lg:flex-col lg:justify-between">
        <div className="auth-reveal relative z-10 flex items-center gap-2" style={{ animationDelay: '120ms' }}>
          <span className="font-display text-2xl tracking-tight">AI Semantic Layer</span>
          <span className="font-mono text-[10px] text-background/50">TM</span>
        </div>
        <div className="auth-reveal relative z-10 max-w-lg pb-4" style={{ animationDelay: '260ms' }}>
          <p className="mb-4 flex items-center gap-2 font-mono text-xs uppercase tracking-[0.22em] text-background/50">
            <Sparkles className="h-3.5 w-3.5" /> Nền tảng quản trị chỉ số
          </p>
          <h1 className="font-display text-5xl leading-[0.95] tracking-tight xl:text-6xl">
            Xây dựng Semantic Layer <span className="text-background/45">cho doanh nghiệp.</span>
          </h1>
          <p className="mt-6 max-w-md text-sm leading-relaxed text-background/60">
            Introspect schema, đề xuất tên nghiệp vụ và quản trị Business Metrics với HITL Workflow an toàn, chính xác.
          </p>
        </div>
        <div className="relative z-10 flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.18em] text-background/40">
          <span>AI Semantic Layer / 2026</span>
          <span>Define with intent</span>
        </div>
        <div className="auth-sphere absolute -right-40 -top-16 w-[56rem] h-[56rem] lg:w-[64rem] lg:h-[64rem] xl:w-[70rem] xl:h-[70rem] opacity-80 pointer-events-none" aria-hidden="true">
          <AnimatedSphere color="255, 255, 255" />
        </div>
        <div className="auth-orbit auth-orbit-one absolute -right-24 -top-6 w-[46rem] h-[46rem] rounded-full border border-background/15 pointer-events-none" />
        <div className="auth-orbit auth-orbit-two absolute right-4 top-16 w-[34rem] h-[34rem] rounded-full border border-background/10 pointer-events-none" />
      </section>

      {/* Form Panel */}
      <section className="flex h-full max-h-screen flex-col justify-between overflow-y-auto px-6 py-5 sm:px-10 lg:px-16 xl:px-24">
        {/* Top Header */}
        <div className="auth-reveal shrink-0 flex items-center justify-between lg:justify-end" style={{ animationDelay: '80ms' }}>
          <Link href="/" className="font-display text-xl tracking-tight lg:hidden">AI Semantic Layer</Link>
          <p className="text-xs sm:text-sm text-muted-foreground">
            {isRegister ? 'Đã có tài khoản?' : 'Chưa có tài khoản?'}{' '}
            <Link
              href={isRegister ? '/login' : '/register'}
              className="font-medium text-foreground underline underline-offset-4 hover:text-muted-foreground"
            >
              {isRegister ? 'Đăng nhập' : 'Tạo tài khoản mới'}
            </Link>
          </p>
        </div>

        {/* Main Form Content - Centered without vertical overflow */}
        <div className="auth-form-content mx-auto my-auto flex w-full max-w-md flex-col justify-center py-2">
          <div className="mb-4 sm:mb-5">
            <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              {isRegister ? '01 / Tham gia nền tảng' : '01 / Chào mừng trở lại'}
            </p>
            <h2 className="font-display text-3xl sm:text-4xl lg:text-5xl tracking-tight">
              {isRegister ? 'Bắt đầu tạo tài khoản.' : 'Chào mừng trở lại.'}
            </h2>
            <p className="mt-2 text-xs sm:text-sm text-muted-foreground">
              {isRegister
                ? 'Tạo tài khoản và bắt đầu quản trị Semantic Layer của bạn.'
                : 'Đăng nhập để tiếp tục xây dựng và quản trị chỉ số.'}
            </p>
          </div>

          {/* Google Login */}
          <div className="grid grid-cols-1 gap-2">
            <GoogleLogin
              onSuccess={async (credentialResponse) => {
                if (credentialResponse.credential) {
                  try {
                    setError('');
                    await loginWithGoogle(credentialResponse.credential);
                    router.push('/workspace');
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
              text={isRegister ? 'signup_with' : 'signin_with'}
            />
          </div>

          <div className="my-3 sm:my-4 flex items-center gap-4 text-[10px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
            <span className="h-px flex-1 bg-foreground/10" />
            hoặc tiếp tục với email
            <span className="h-px flex-1 bg-foreground/10" />
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-3 p-2.5 bg-destructive/10 border border-destructive/30 text-destructive rounded-xl text-xs text-center font-medium">
              {error}
            </div>
          )}

          {/* Form Fields */}
          <form className="space-y-3 sm:space-y-3.5" onSubmit={handleSubmit}>
            {isRegister && (
              <label className="block space-y-1">
                <span className="text-xs font-medium">Họ và Tên</span>
                <span className="relative block">
                  <User className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    required
                    className="h-10 sm:h-11 w-full rounded-xl border border-foreground/15 bg-transparent pl-10 pr-4 text-xs sm:text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-foreground"
                    placeholder="Nguyễn Văn A"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </span>
              </label>
            )}

            <label className="block space-y-1">
              <span className="text-xs font-medium">Email</span>
              <span className="relative block">
                <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  required
                  type="email"
                  className="h-10 sm:h-11 w-full rounded-xl border border-foreground/15 bg-transparent pl-10 pr-4 text-xs sm:text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-foreground"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </span>
            </label>

            <label className="block space-y-1">
              <span className="text-xs font-medium">Mật khẩu</span>
              <span className="relative block">
                <LockKeyhole className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  required
                  type={showPassword ? 'text' : 'password'}
                  minLength={8}
                  className="h-10 sm:h-11 w-full rounded-xl border border-foreground/15 bg-transparent pl-10 pr-10 text-xs sm:text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-foreground"
                  placeholder={isRegister ? 'Ít nhất 8 ký tự' : 'Nhập mật khẩu'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </span>
            </label>

            {isRegister && (
              <label className="block space-y-1">
                <span className="text-xs font-medium">Xác nhận Mật khẩu</span>
                <span className="relative block">
                  <Lock className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    required
                    type={showPassword ? 'text' : 'password'}
                    minLength={8}
                    className="h-10 sm:h-11 w-full rounded-xl border border-foreground/15 bg-transparent pl-10 pr-4 text-xs sm:text-sm outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-foreground"
                    placeholder="Nhập lại mật khẩu"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                </span>
              </label>
            )}

            {!isRegister && (
              <div className="flex justify-end">
                <Link href="#" className="text-[11px] text-muted-foreground underline underline-offset-4 hover:text-foreground">
                  Quên mật khẩu?
                </Link>
              </div>
            )}

            <Button
              className="group h-10 sm:h-11 w-full rounded-full bg-foreground text-background hover:bg-foreground/85 cursor-pointer text-xs sm:text-sm mt-1"
              type="submit"
              disabled={loading}
            >
              {loading
                ? isRegister ? 'Đang tạo tài khoản...' : 'Đang xử lý...'
                : isRegister ? 'Tạo tài khoản' : 'Đăng nhập'}
              <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Button>
          </form>

          <p className="mt-3 text-center text-[10px] sm:text-xs text-muted-foreground">
            Bằng cách tiếp tục, bạn đồng ý với điều khoản của AI Semantic Layer.
          </p>
        </div>

        {/* Bottom Footer */}
        <div className="shrink-0 flex justify-between border-t border-foreground/10 pt-3 text-[10px] font-mono uppercase tracking-[0.16em] text-muted-foreground">
          <span>Bảo mật an toàn</span>
          <Link href="/" className="hover:text-foreground">Về trang chủ</Link>
        </div>
      </section>
    </main>
  );
}

export default AuthForm;
