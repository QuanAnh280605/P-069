'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function LegacyReviewPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/');
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-[#0B0F19] text-xs text-slate-500 font-semibold">
      Đang chuyển hướng sang AI ChatGPT Agent Workspace...
    </div>
  );
}
