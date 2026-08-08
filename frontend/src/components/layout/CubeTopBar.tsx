'use client';

import React from 'react';
import {
  Save,
  Share2,
  CheckCircle2,
  Clock,
  Sparkles,
  Sun,
  Moon,
  Database,
  Layers,
  BarChart3,
} from 'lucide-react';
import { CubeNavTab } from './CubeSidebar';

interface CubeTopBarProps {
  dbName: string;
  status: 'Draft' | 'Saved';
  activeTab: CubeNavTab;
  onTabChange: (tab: CubeNavTab) => void;
  onSaveOfficial: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export const CubeTopBar: React.FC<CubeTopBarProps> = ({
  dbName,
  status,
  activeTab,
  onTabChange,
  onSaveOfficial,
  theme,
  onToggleTheme,
}) => {
  const isDark = theme === 'dark';

  const getTabTitle = (tab: CubeNavTab) => {
    switch (tab) {
      case 'studio':
        return { label: 'AI Metric Studio (Copilot)', icon: <Sparkles className="w-3.5 h-3.5 text-indigo-500" /> };
      case 'tables':
        return { label: 'Data Modeling & Schema', icon: <Layers className="w-3.5 h-3.5 text-sky-500" /> };
      case 'metrics':
        return { label: 'Business Metrics Catalog', icon: <BarChart3 className="w-3.5 h-3.5 text-emerald-500" /> };
      case 'export':
        return { label: 'Export & Code Integration', icon: <Share2 className="w-3.5 h-3.5 text-purple-500" /> };
    }
  };

  const currentTab = getTabTitle(activeTab);

  return (
    <header
      className={`px-6 py-3.5 border-b flex flex-col md:flex-row items-start md:items-center justify-between gap-3 sticky top-0 z-40 transition-colors ${
        isDark
          ? 'bg-[#0B0F19]/95 backdrop-blur-md border-slate-800 text-slate-100'
          : 'bg-white/95 backdrop-blur-md border-slate-200 text-slate-800 shadow-2xs'
      }`}
    >
      {/* Left: Breadcrumbs & Current DB Status */}
      <div className="flex items-center gap-2.5 flex-wrap">
        <div className={`flex items-center gap-1.5 text-xs ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
          <Database className="w-3.5 h-3.5 text-slate-400" />
          <span>Workspace</span>
          <span>/</span>
          <span className="font-bold text-indigo-600 dark:text-indigo-400">{dbName}</span>
          <span>/</span>
        </div>

        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-bold ${
            isDark
              ? 'bg-slate-900 border-slate-800 text-slate-200'
              : 'bg-slate-100/80 border-slate-200 text-slate-800'
          }`}
        >
          {currentTab.icon}
          <span>{currentTab.label}</span>
        </div>

        {status === 'Saved' ? (
          <span
            className={`text-[11px] font-bold px-2 py-0.5 rounded-full inline-flex items-center gap-1 border ${
              isDark
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                : 'bg-emerald-50 text-emerald-700 border-emerald-200'
            }`}
          >
            <CheckCircle2 className="w-3 h-3" /> Saved (Production)
          </span>
        ) : (
          <span
            className={`text-[11px] font-bold px-2 py-0.5 rounded-full inline-flex items-center gap-1 border ${
              isDark
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                : 'bg-amber-50 text-amber-700 border-amber-200'
            }`}
          >
            <Clock className="w-3 h-3" /> Draft (Editing)
          </span>
        )}
      </div>

      {/* Right: Quick Action Controls & Theme Toggle */}
      <div className="flex items-center gap-2.5 w-full md:w-auto justify-end">
        {/* Theme Switcher Button on Header */}
        <button
          onClick={onToggleTheme}
          className={`p-2 rounded-xl border transition-all cursor-pointer shadow-2xs flex items-center justify-center ${
            isDark
              ? 'bg-slate-900 hover:bg-slate-800 border-slate-700 text-amber-400 hover:text-amber-300'
              : 'bg-white hover:bg-slate-100 border-slate-200 text-slate-700 hover:text-indigo-600'
          }`}
          title={isDark ? 'Chuyển sang Giao diện Sáng (Light Theme)' : 'Chuyển sang Giao diện Tối (Dark Theme)'}
        >
          {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* Quick AI Studio Button */}
        {activeTab !== 'studio' && (
          <button
            onClick={() => onTabChange('studio')}
            className={`px-3.5 py-2 text-xs font-bold rounded-xl border transition-all cursor-pointer flex items-center gap-1.5 shadow-2xs ${
              isDark
                ? 'text-indigo-300 bg-indigo-950/60 hover:bg-indigo-900/80 border-indigo-800'
                : 'text-indigo-900 bg-indigo-50 hover:bg-indigo-100 border-indigo-200'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-500" />
            <span>✨ AI Studio</span>
          </button>
        )}

        {/* Export Button */}
        {activeTab !== 'export' && (
          <button
            onClick={() => onTabChange('export')}
            className={`px-3.5 py-2 text-xs font-semibold rounded-xl border transition-all cursor-pointer flex items-center gap-1.5 shadow-2xs ${
              isDark
                ? 'bg-slate-900 hover:bg-slate-800 border-slate-700 text-slate-200'
                : 'bg-white hover:bg-slate-50 border-slate-300 text-slate-700'
            }`}
          >
            <Share2 className="w-3.5 h-3.5 text-purple-500" />
            <span>Export Code</span>
          </button>
        )}

        {/* Save Official Button */}
        <button
          onClick={onSaveOfficial}
          className="gradient-btn px-4 py-2 text-xs font-bold text-white rounded-xl shadow-md flex items-center gap-1.5 cursor-pointer hover:opacity-95"
        >
          <Save className="w-3.5 h-3.5" />
          <span>Lưu Chính Thức</span>
        </button>
      </div>
    </header>
  );
};
