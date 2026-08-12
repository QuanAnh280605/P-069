import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';

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
    <html lang="vi" suppressHydrationWarning>
      <body className="antialiased selection:bg-indigo-500 selection:text-white min-h-screen w-full overflow-x-hidden transition-colors duration-200" suppressHydrationWarning>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
