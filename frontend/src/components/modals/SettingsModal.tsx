'use client';

import React from 'react';
import { X, Settings, ShieldCheck, Sun, Moon, Sparkles, Key } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose }) => {
  const { user, token } = useAuth();
  const { theme, setTheme } = useTheme();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 dark:bg-slate-950/70 backdrop-blur-sm animate-in fade-in">
      <div className="glass-card w-full max-w-xl rounded-2xl border border-indigo-500/30 shadow-2xl overflow-hidden bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 dark:bg-indigo-500/20 text-indigo-600 dark:text-indigo-400 flex items-center justify-center border border-indigo-200 dark:border-indigo-500/30">
              <Settings className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold tracking-tight text-slate-900 dark:text-white">Cấu hình Hệ thống & Tùy chọn</h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">AI Semantic Layer Agent Platform</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 dark:hover:text-white p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Settings Body */}
        <div className="p-6 space-y-5 text-xs">
          {/* Theme Selection Section */}
          <div className="space-y-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              🎨 Giao diện (App Theme)
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setTheme('light')}
                className={`p-3 rounded-xl border flex items-center justify-center gap-2.5 transition-all font-semibold cursor-pointer ${
                  theme === 'light'
                    ? 'bg-indigo-50 border-indigo-500 text-indigo-700 shadow-xs'
                    : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-400 hover:border-slate-300'
                }`}
              >
                <Sun className="w-4 h-4 text-amber-500" />
                <span>Giao diện Sáng (Light)</span>
              </button>

              <button
                type="button"
                onClick={() => setTheme('dark')}
                className={`p-3 rounded-xl border flex items-center justify-center gap-2.5 transition-all font-semibold cursor-pointer ${
                  theme === 'dark'
                    ? 'bg-indigo-950/80 border-indigo-500 text-indigo-300 shadow-xs'
                    : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-400 hover:border-slate-300'
                }`}
              >
                <Moon className="w-4 h-4 text-indigo-400" />
                <span>Giao diện Tối (Dark)</span>
              </button>
            </div>
          </div>

          {/* System & Backend Info Section */}
          <div className="space-y-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              ⚡ KẾT NỐI AI BACKEND ENGINE
            </label>
            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-2 font-mono">
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">API Endpoint:</span>
                <span className="font-bold text-indigo-600 dark:text-indigo-400">http://localhost:8000</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">LLM Provider:</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                  <Sparkles className="w-3 h-3" /> LangGraph + SQLAlchemy Inspector
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">Query Compiler:</span>
                <span className="font-bold text-cyan-600 dark:text-cyan-400">SemanticQueryCompiler v1.0</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-600 dark:text-slate-400">Security Guardrails:</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> Fernet Encrypted + READ-ONLY SELECT
                </span>
              </div>
            </div>
          </div>

          {/* Auth Token Info */}
          <div className="space-y-2">
            <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              🔒 THÔNG TIN TÀI KHOẢN & JWT TOKEN
            </label>
            <div className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 space-y-1.5 font-mono">
              {user ? (
                <>
                  <div className="flex items-center justify-between text-slate-900 dark:text-slate-200 font-sans">
                    <span>Đã đăng nhập: <b>{user.name}</b> ({user.email})</span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 font-bold border border-emerald-200 dark:border-emerald-500/30">
                      Active
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-600 dark:text-slate-400 truncate flex items-center gap-1 pt-1">
                    <Key className="w-3 h-3 text-amber-500 shrink-0" /> Token: {token ? `${token.slice(0, 28)}...` : 'N/A (Local Session)'}
                  </div>
                </>
              ) : (
                <div className="text-slate-700 dark:text-slate-300 font-sans flex items-center justify-between">
                  <span>Chưa đăng nhập (Chế độ xem Thử nghiệm Offline)</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-500/20 text-amber-800 dark:text-amber-400 font-bold border border-amber-200 dark:border-amber-500/30">
                    Guest Mode
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-end bg-slate-50 dark:bg-slate-950">
          <button
            onClick={onClose}
            className="gradient-btn px-5 py-2 text-xs font-bold text-white rounded-xl shadow-md cursor-pointer"
          >
            Đóng Cấu Hình
          </button>
        </div>
      </div>
    </div>
  );
};
