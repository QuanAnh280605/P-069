'use client';

import React from 'react';
import Link from 'next/link';
import {
  Database,
  BarChart3,
  Sparkles,
  Share2,
  ArrowLeft,
  LogOut,
  User,
  Activity,
} from 'lucide-react';

export type CubeNavTab = 'metrics' | 'studio' | 'export';

interface CubeSidebarProps {
  activeTab: CubeNavTab;
  onTabChange: (tab: CubeNavTab) => void;
  theme: 'light' | 'dark';
  dbName: string;
  dbType?: string;
  metricCount: number;
  tableCount: number;
  user: { name?: string; email?: string; avatar?: string } | null;
  onLogout: () => void;
}

export const CubeSidebar: React.FC<CubeSidebarProps> = ({
  activeTab,
  onTabChange,
  theme,
  dbName,
  dbType = 'postgresql',
  metricCount,
  tableCount: _tableCount,
  user,
  onLogout,
}) => {
  const isDark = theme === 'dark';

  const navItems: { id: CubeNavTab; label: string; icon: React.ReactNode; badge?: string }[] = [
    {
      id: 'studio',
      label: 'AI Metric Studio',
      icon: <Sparkles className="w-4 h-4 text-indigo-500 dark:text-indigo-400" />,
      badge: 'AI Live',
    },
    {
      id: 'metrics',
      label: 'Metrics Catalog',
      icon: <BarChart3 className="w-4 h-4 text-emerald-500 dark:text-emerald-400" />,
      badge: `${metricCount}`,
    },
    {
      id: 'export',
      label: 'Export & Code',
      icon: <Share2 className="w-4 h-4 text-purple-500 dark:text-purple-400" />,
    },
  ];

  return (
    <aside
      className={`w-64 flex flex-col justify-between border-r select-none shrink-0 h-screen sticky top-0 transition-colors duration-150 ${
        isDark
          ? 'bg-[#0B0F19] text-slate-300 border-slate-800'
          : 'bg-white text-slate-800 border-slate-200 shadow-2xs'
      }`}
    >
      {/* Brand Header */}
      <div>
        <div
          className={`p-4 border-b flex items-center justify-between ${
            isDark ? 'border-slate-800/80 bg-slate-950/40' : 'border-slate-100 bg-slate-50/70'
          }`}
        >
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-cyan-400 p-0.5 shadow-md group-hover:scale-105 transition-transform">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <Database className="w-4 h-4 text-indigo-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className={`font-extrabold text-sm tracking-wider ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  S206
                </span>
                <span className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-500/20 border border-indigo-200 dark:border-indigo-500/30 px-1.5 py-0.2 rounded-full uppercase">
                  Semantic
                </span>
              </div>
              <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium block">Governance Platform</span>
            </div>
          </Link>

          <Link
            href="/"
            className={`p-1.5 rounded-lg transition-all ${
              isDark
                ? 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100'
            }`}
            title="Quay lại Dashboard"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
        </div>

        {/* Database Context Selector Badge */}
        <div
          className={`px-4 py-3 border-b ${
            isDark ? 'border-slate-800/60 bg-slate-900/40' : 'border-slate-100 bg-slate-50/50'
          }`}
        >
          <div className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">
            Active Data Source
          </div>
          <div
            className={`flex items-center justify-between gap-2 p-2 rounded-lg border text-xs ${
              isDark
                ? 'bg-slate-950/80 border-slate-800'
                : 'bg-white border-slate-200 shadow-2xs'
            }`}
          >
            <div className="flex items-center gap-2 truncate">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shrink-0" />
              <span className={`font-bold truncate ${isDark ? 'text-white' : 'text-slate-900'}`}>
                {dbName}
              </span>
            </div>
            <span
              className={`text-[10px] font-mono uppercase px-1.5 py-0.5 rounded font-semibold ${
                isDark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-700'
              }`}
            >
              {dbType}
            </span>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="p-3 space-y-1">
          <div className="px-3 py-1 text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Workspace Views
          </div>
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  isActive
                    ? isDark
                      ? 'bg-indigo-600/20 text-white border border-indigo-500/40 shadow-xs'
                      : 'bg-indigo-50 text-indigo-900 border border-indigo-200 shadow-2xs font-bold'
                    : isDark
                    ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent'
                    : 'text-slate-700 hover:text-slate-950 hover:bg-slate-100 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  {item.icon}
                  <span className={isActive ? (isDark ? 'font-bold text-white' : 'font-bold text-indigo-950') : ''}>
                    {item.label}
                  </span>
                </div>
                {item.badge && (
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                      isActive
                        ? isDark
                          ? 'bg-indigo-500/30 text-indigo-300 border border-indigo-500/40'
                          : 'bg-indigo-100 text-indigo-800 font-bold'
                        : isDark
                        ? 'bg-slate-800/80 text-slate-400'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer Controls: User Info & AST Engine Status */}
      <div
        className={`p-3 border-t space-y-2.5 ${
          isDark ? 'border-slate-800/70 bg-slate-950/60' : 'border-slate-100 bg-slate-50/70'
        }`}
      >
        {/* Status indicator */}
        <div className="flex items-center justify-between text-[11px] px-1 font-medium text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
            <Activity className="w-3.5 h-3.5 text-emerald-500" /> AST Engine: Safe
          </span>
          <span className="font-mono text-[10px]">v1.0.0</span>
        </div>

        {/* User Card */}
        {user && (
          <div
            className={`flex items-center justify-between p-2 rounded-xl border ${
              isDark
                ? 'bg-slate-900 border-slate-800'
                : 'bg-white border-slate-200 shadow-2xs'
            }`}
          >
            <div className="flex items-center gap-2 truncate">
              {user.avatar ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={user.avatar} alt="user" className="w-6 h-6 rounded-full border border-indigo-400" />
              ) : (
                <div className="w-6 h-6 rounded-full bg-indigo-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                  <User className="w-3 h-3" />
                </div>
              )}
              <span
                className={`text-xs font-bold truncate ${
                  isDark ? 'text-slate-200' : 'text-slate-800'
                }`}
              >
                {user.name || 'Analyst'}
              </span>
            </div>
            <button
              onClick={onLogout}
              className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                isDark
                  ? 'text-slate-400 hover:text-red-400 hover:bg-slate-800'
                  : 'text-slate-500 hover:text-red-600 hover:bg-red-50'
              }`}
              title="Đăng xuất"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
};
