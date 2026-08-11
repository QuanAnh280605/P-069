'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { SettingsModal } from '@/components/modals/SettingsModal';
import { Database, LogOut, FileText, Settings, Sparkles, Sun, Moon } from 'lucide-react';

export const Header: React.FC = () => {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = theme === 'dark';

  return (
    <>
      <header className="glass-header sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between transition-colors">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-cyan-400 p-0.5 shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Database className="w-5 h-5 text-indigo-400" />
            </div>
          </div>
          <div>
            <span className="font-bold text-lg tracking-wide gradient-text block leading-none">
              S206 SEMANTIC LAYER
            </span>
            <span className="text-[10px] text-slate-500 dark:text-slate-400 tracking-wider font-semibold uppercase">
              Agent Governance Platform
            </span>
          </div>
        </Link>

        {/* Navigation Links, Theme Toggle & User Menu */}
        <div className="flex items-center gap-4 md:gap-6">
          <nav className="hidden md:flex items-center gap-5 text-sm font-medium text-slate-700 dark:text-slate-300">
            <Link href="/" className="hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors flex items-center gap-1.5">
              <Database className="w-4 h-4 text-slate-400" /> Dashboard
            </Link>
            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer"
              className="hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors flex items-center gap-1.5"
            >
              <FileText className="w-4 h-4 text-slate-400" /> Docs
            </a>
            <button
              onClick={() => setSettingsOpen(true)}
              className="hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Settings className="w-4 h-4 text-slate-400" /> Settings
            </button>
          </nav>

          {/* Global Theme Toggle Button */}
          {mounted && (
            <button
              onClick={toggleTheme}
              className={`p-2 rounded-xl border transition-all cursor-pointer shadow-xs flex items-center justify-center ${
                isDark
                  ? 'bg-slate-900 hover:bg-slate-800 border-slate-700 text-amber-400 hover:text-amber-300'
                  : 'bg-white hover:bg-slate-100 border-slate-200 text-slate-700 hover:text-indigo-600'
              }`}
              title={isDark ? 'Chuyển sang Giao diện Sáng (Light Theme)' : 'Chuyển sang Giao diện Tối (Dark Theme)'}
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          )}

          {mounted && user ? (
            <div className="relative">
              <button
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-900/80 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700/60 rounded-full py-1.5 px-3 transition-all cursor-pointer"
              >
                {user.avatar ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={user.avatar} alt={user.name} className="w-6 h-6 rounded-full border border-indigo-400" />
                ) : (
                  <div className="w-6 h-6 rounded-full bg-indigo-600 flex items-center justify-center text-xs text-white font-bold">
                    {user.name.charAt(0).toUpperCase()}
                  </div>
                )}
                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{user.name}</span>
              </button>

              {dropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 glass-card rounded-xl shadow-2xl py-2 z-50 border border-slate-200 dark:border-slate-700/80 animate-in fade-in slide-in-from-top-2 bg-white dark:bg-slate-900">
                  <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-800">
                    <p className="text-xs font-bold text-slate-900 dark:text-slate-200">{user.name}</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">{user.email}</p>
                    <div className="mt-1 flex items-center gap-1 text-[10px] text-cyan-600 dark:text-cyan-400">
                      <Sparkles className="w-3 h-3" /> Provider: {user.provider || 'JWT Auth'}
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setDropdownOpen(false);
                      logout();
                    }}
                    className="w-full text-left px-4 py-2 text-xs text-red-500 dark:text-red-400 hover:bg-red-500/10 flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    <LogOut className="w-3.5 h-3.5" /> Đăng xuất
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <Link
                href="/login"
                className="text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-indigo-600 dark:hover:text-white px-3 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                Đăng nhập
              </Link>
              <Link
                href="/register"
                className="gradient-btn text-xs font-semibold text-white px-3.5 py-1.5 rounded-lg shadow-md"
              >
                Đăng ký
              </Link>
            </div>
          )}
        </div>
      </header>

      {/* Real Settings Modal */}
      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
};
