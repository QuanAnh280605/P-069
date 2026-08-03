import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';
import { Header } from '@/components/layout/Header';

export const metadata: Metadata = {
  title: 'AI Semantic Layer Agent — Governance Platform',
  description:
    'Hệ thống AI Agent tự động Introspect DB schema, đề xuất tên nghiệp vụ & Business Metrics và quản trị Semantic Layer với HITL Workflow',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className="dark" suppressHydrationWarning>
      <body className="antialiased selection:bg-indigo-500 selection:text-white" suppressHydrationWarning>
        <Providers>
          <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-8">{children}</main>
            <footer className="py-6 border-t border-slate-800/60 text-center text-xs text-slate-500">
              © 2026 AI Semantic Layer Agent. All rights reserved. Managed with JWT & Google Auth.
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
