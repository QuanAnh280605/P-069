'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { ConnectDbModal } from '@/components/modals/ConnectDbModal';
import { SettingsModal } from '@/components/modals/SettingsModal';
import { MetricModal } from '@/components/modals/MetricModal';
import { AIStudioView } from '@/components/views/AIStudioView';
import { MetricsCatalogView } from '@/components/views/MetricsCatalogView';
import { ExportPlaygroundView } from '@/components/views/ExportPlaygroundView';
import { getLocalLayers, updateLayer, deleteLayer, SemanticLayerData, BusinessMetric, MetricSuggestion, deleteMetricApi } from '@/lib/api';
import {
  Database,
  PlusCircle,
  Sparkles,
  BarChart3,
  Share2,
  Sun,
  Moon,
  Settings,
  LogOut,
  Loader2,
  Trash2,
  CheckCircle2,
  ShieldCheck,
} from 'lucide-react';

export type CubeNavTab = 'studio' | 'metrics' | 'export';

export default function ChatGPTDashboardPage() {
  const { user, logout, isLoading } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  const [layers, setLayers] = useState<SemanticLayerData[]>([]);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<CubeNavTab>('studio');

  // Modals
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);
  const [isMetricModalOpen, setIsMetricModalOpen] = useState(false);
  const [editingMetric, setEditingMetric] = useState<BusinessMetric | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    const local = getLocalLayers();
    setLayers(local);
    if (local.length > 0) {
      setSelectedLayerId(local[0].id);
    }
  }, []);

  const refreshLayers = (preferredId?: string) => {
    const updated = getLocalLayers();
    setLayers(updated);
    if (preferredId) {
      setSelectedLayerId(preferredId);
    } else if (updated.length > 0 && !selectedLayerId) {
      setSelectedLayerId(updated[0].id);
    }
  };

  const activeLayer = layers.find((l) => l.id === selectedLayerId) || layers[0] || null;

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleDbConnectedSuccess = (newDbName: string, newDbId?: string) => {
    refreshLayers(newDbId);
    showToast(`🎉 Đã kết nối thành công Database "${newDbName}"!`);
  };

  const handleDeleteDb = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Bạn có chắc chắn muốn xóa kết nối Database này?')) {
      deleteLayer(id);
      const remaining = getLocalLayers();
      setLayers(remaining);
      if (selectedLayerId === id) {
        setSelectedLayerId(remaining.length > 0 ? remaining[0].id : null);
      }
      showToast('🗑️ Đã xóa kết nối Database.');
    }
  };

  const handleSaveMetric = (savedMetric: BusinessMetric) => {
    if (!activeLayer) return;
    const existingIdx = activeLayer.metrics.findIndex((m) => m.id === savedMetric.id);
    let updatedMetrics = [...activeLayer.metrics];
    if (existingIdx >= 0) {
      updatedMetrics[existingIdx] = savedMetric;
    } else {
      updatedMetrics = [...activeLayer.metrics, savedMetric];
    }
    const updatedLayer = { ...activeLayer, metrics: updatedMetrics, status: 'Draft' as const };
    updateLayer(updatedLayer);
    refreshLayers(activeLayer.id);
    setIsMetricModalOpen(false);
    showToast(`✅ Đã cập nhật chỉ số "${savedMetric.name}"!`);
  };

  const handleDeleteMetric = async (mId: string) => {
    if (!activeLayer) return;
    try {
      await deleteMetricApi(activeLayer.id, mId);
    } catch {
      // offline fallback
    }
    const updatedMetrics = activeLayer.metrics.filter((m) => m.id !== mId);
    const updatedLayer = { ...activeLayer, metrics: updatedMetrics, status: 'Draft' as const };
    updateLayer(updatedLayer);
    refreshLayers(activeLayer.id);
    showToast('🗑️ Đã xóa chỉ số khỏi thư viện.');
  };

  const handleAddMetricFromStudio = (newMetric: MetricSuggestion) => {
    if (!activeLayer) return;
    const localMetric: BusinessMetric = {
      id: `m_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      name: newMetric.name,
      description: newMetric.description,
      sql_template: newMetric.sql_template,
      source: 'ai',
      created_at: new Date().toISOString(),
    };
    const updatedMetrics = [...activeLayer.metrics, localMetric];
    const updatedLayer = { ...activeLayer, metrics: updatedMetrics, status: 'Draft' as const };
    updateLayer(updatedLayer);
    refreshLayers(activeLayer.id);
  };

  const handleEditSuggestion = (sugg: MetricSuggestion) => {
    const draftId = `draft_${Math.random().toString(36).slice(2, 9)}`;
    setEditingMetric({
      id: draftId,
      name: sugg.name,
      description: sugg.description,
      sql_template: sugg.sql_template,
      source: 'ai',
    });
    setIsMetricModalOpen(true);
  };

  if (!mounted || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-[#0B0F19] text-indigo-600 dark:text-indigo-400">
        <div className="flex items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin" />
          <span className="text-sm font-semibold">Đang khởi tạo AI Agent Workspace...</span>
        </div>
      </div>
    );
  }

  const isDark = theme === 'dark';

  return (
    <div className={`min-h-screen flex h-screen overflow-hidden transition-colors ${isDark ? 'bg-[#0B0F19] text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-6 right-6 z-60 bg-slate-900 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-xl border border-slate-700 animate-in slide-in-from-top flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* LEFT SIDEBAR (ChatGPT Style) */}
      <aside className={`w-64 md:w-72 flex flex-col justify-between border-r shrink-0 h-screen sticky top-0 transition-colors select-none ${isDark ? 'bg-[#0E1526] border-slate-800' : 'bg-white border-slate-200 shadow-2xs'}`}>
        <div>
          {/* Brand Header */}
          <div className={`p-4 border-b flex items-center justify-between transition-colors ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
            <Link href="/" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-cyan-400 p-0.5 shadow-md group-hover:scale-105 transition-transform">
                <div className={`w-full h-full rounded-[10px] flex items-center justify-center ${isDark ? 'bg-slate-950' : 'bg-white'}`}>
                  <Database className="w-4.5 h-4.5 text-indigo-600 dark:text-indigo-400" />
                </div>
              </div>
              <div>
                <span className="font-extrabold text-sm tracking-wider gradient-text block leading-none">
                  S206 SEMANTIC
                </span>
                <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium">AI Agent Governance</span>
              </div>
            </Link>

            <button
              onClick={toggleTheme}
              className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                isDark
                  ? 'border-slate-800 text-slate-400 hover:text-amber-400 hover:bg-slate-800'
                  : 'border-slate-200 text-slate-600 hover:text-indigo-600 hover:bg-slate-100'
              }`}
              title={isDark ? 'Chuyển sang Light Theme' : 'Chuyển sang Dark Theme'}
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>

          {/* New Connection Button */}
          <div className="p-3">
            <button
              onClick={() => setIsConnectModalOpen(true)}
              className="gradient-btn w-full py-2.5 px-3 text-xs font-bold text-white rounded-xl shadow-md flex items-center justify-center gap-2 cursor-pointer hover:opacity-95"
            >
              <PlusCircle className="w-4 h-4" />
              <span>➕ Thêm Kết Nối Database</span>
            </button>
          </div>

          {/* Connected Databases List Header */}
          <div className={`px-4 py-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
            <span>Danh sách Database ({layers.length})</span>
            <Database className="w-3.5 h-3.5 text-slate-400" />
          </div>

          {/* Connected Databases Items */}
          <div className="px-3 overflow-y-auto max-h-[calc(100vh-280px)] space-y-1">
            {layers.length === 0 ? (
              <div className={`p-4 text-center text-xs border border-dashed rounded-xl my-2 ${isDark ? 'text-slate-400 border-slate-800' : 'text-slate-500 border-slate-200'}`}>
                Chưa có DB nào.
                <br />
                Hãy bấm nút ở trên để thêm kết nối.
              </div>
            ) : (
              layers.map((layer) => {
                const isSelected = layer.id === selectedLayerId;
                return (
                  <div
                    key={layer.id}
                    onClick={() => {
                      setSelectedLayerId(layer.id);
                      setActiveTab('studio');
                    }}
                    className={`p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-2 group ${
                      isSelected
                        ? isDark
                          ? 'bg-indigo-950/80 border-indigo-500/80 shadow-xs'
                          : 'bg-indigo-50 border-indigo-300 shadow-2xs'
                        : isDark
                        ? 'bg-slate-900/40 hover:bg-slate-900 border-slate-800 text-slate-300'
                        : 'bg-slate-50 hover:bg-slate-100 border-slate-200 text-slate-800'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                        <span className={`text-xs font-bold truncate ${isSelected ? (isDark ? 'text-white' : 'text-indigo-950') : (isDark ? 'text-slate-200' : 'text-slate-800')}`}>
                          {layer.db_name}
                        </span>
                      </div>
                      <div className={`text-[10px] truncate mt-0.5 font-mono ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                        {layer.db_type.toUpperCase()} • {layer.tables.length} bảng • {layer.metrics.length} metrics
                      </div>
                    </div>

                    <button
                      onClick={(e) => handleDeleteDb(layer.id, e)}
                      className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 transition-opacity cursor-pointer"
                      title="Xóa DB"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Footer User Info & Settings */}
        <div className={`p-3 border-t space-y-2 transition-colors ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
          <div className="flex items-center justify-between">
            <button
              onClick={() => setIsSettingsModalOpen(true)}
              className={`flex items-center gap-1.5 text-xs font-semibold cursor-pointer transition-colors ${
                isDark ? 'text-slate-300 hover:text-indigo-400' : 'text-slate-700 hover:text-indigo-600'
              }`}
            >
              <Settings className="w-3.5 h-3.5 text-slate-500" /> Cấu hình System
            </button>
            <span className={`text-[10px] font-mono ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>AST Validated</span>
          </div>

          {user && (
            <div className={`flex items-center justify-between p-2 rounded-xl border transition-colors ${isDark ? 'bg-slate-900 border-slate-800' : 'bg-slate-100 border-slate-200'}`}>
              <div className="flex items-center gap-2 truncate">
                <div className="w-6 h-6 rounded-full bg-indigo-600 text-white text-[10px] font-bold flex items-center justify-center shrink-0">
                  {user.name.charAt(0).toUpperCase()}
                </div>
                <span className={`text-xs font-bold truncate ${isDark ? 'text-slate-100' : 'text-slate-900'}`}>{user.name}</span>
              </div>
              <button
                onClick={logout}
                className="p-1 text-slate-400 hover:text-red-500 cursor-pointer"
                title="Đăng xuất"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* CENTER WORKSPACE CANVAS */}
      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {!activeLayer ? (
          /* EMPTY STATE: CENTERED DATABASE CONNECTION BUTTON */
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center animate-in fade-in">
            <div className={`max-w-md w-full glass-card p-8 md:p-10 rounded-3xl border shadow-2xl space-y-5 relative overflow-hidden transition-colors ${
              isDark ? 'bg-slate-900 border-indigo-500/30' : 'bg-white border-slate-200'
            }`}>
              <div className="absolute top-0 right-1/2 translate-x-1/2 w-72 h-72 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />

              <div className="w-16 h-16 rounded-2xl bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mx-auto shadow-xs">
                <Database className="w-8 h-8" />
              </div>

              <div>
                <h1 className={`text-xl md:text-2xl font-extrabold tracking-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Bắt Đầu Với AI Semantic Agent
                </h1>
                <p className={`text-xs md:text-sm mt-2 leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Chưa có Database nào được chọn. Hãy bấm nút bên dưới để kết nối Live Target DB hoặc Import file SQL Dump schema DDL.
                </p>
              </div>

              <button
                onClick={() => setIsConnectModalOpen(true)}
                className="gradient-btn w-full py-3.5 px-6 text-sm font-extrabold text-white rounded-2xl shadow-xl flex items-center justify-center gap-2.5 cursor-pointer hover:scale-[1.02] transition-all"
              >
                <PlusCircle className="w-5 h-5" />
                <span>➕ Thêm Kết Nối Database</span>
              </button>

              <div className={`pt-2 flex items-center justify-center gap-4 text-[11px] ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
                <span className="flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" /> Read-Only Security
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-500" /> LLM Enrich
                </span>
              </div>
            </div>
          </div>
        ) : (
          /* ACTIVE CHAT WORKSPACE */
          <div className="flex-1 flex flex-col h-screen overflow-hidden">
            {/* Top Workspace Bar */}
            <header className={`px-6 py-3 border-b flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shrink-0 transition-colors ${
              isDark ? 'bg-[#0B0F19] border-slate-800 text-slate-100' : 'bg-white border-slate-200 text-slate-900 shadow-2xs'
            }`}>
              <div className="flex items-center gap-2 flex-wrap">
                <div className={`flex items-center gap-1.5 text-xs ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  <Database className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
                  <span>Workspace</span>
                  <span className="text-slate-400">/</span>
                  <span className={`font-bold ${isDark ? 'text-indigo-400' : 'text-indigo-600'}`}>{activeLayer.db_name}</span>
                </div>

                <span className={`text-[11px] font-mono uppercase px-2.5 py-0.5 rounded font-bold border ${
                  isDark ? 'bg-slate-800 text-slate-200 border-slate-700' : 'bg-slate-100 text-slate-800 border-slate-200'
                }`}>
                  {activeLayer.db_type}
                </span>

                <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-500/30 inline-flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> {activeLayer.status}
                </span>
              </div>

              {/* Navigation Tabs */}
              <div className={`flex items-center p-1 rounded-xl border ${
                isDark ? 'bg-slate-900 border-slate-800' : 'bg-slate-100 border-slate-200'
              }`}>
                <button
                  onClick={() => setActiveTab('studio')}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
                    activeTab === 'studio'
                      ? isDark
                        ? 'bg-slate-800 text-indigo-400 shadow-xs font-extrabold'
                        : 'bg-white text-indigo-600 shadow-2xs font-extrabold'
                      : isDark
                      ? 'text-slate-400 hover:text-slate-200'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5 text-indigo-500" /> 💬 AI Chat Studio
                </button>

                <button
                  onClick={() => setActiveTab('metrics')}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
                    activeTab === 'metrics'
                      ? isDark
                        ? 'bg-slate-800 text-indigo-400 shadow-xs font-extrabold'
                        : 'bg-white text-indigo-600 shadow-2xs font-extrabold'
                      : isDark
                      ? 'text-slate-400 hover:text-slate-200'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <BarChart3 className="w-3.5 h-3.5 text-emerald-500" /> Catalog ({activeLayer.metrics.length})
                </button>

                <button
                  onClick={() => setActiveTab('export')}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
                    activeTab === 'export'
                      ? isDark
                        ? 'bg-slate-800 text-indigo-400 shadow-xs font-extrabold'
                        : 'bg-white text-indigo-600 shadow-2xs font-extrabold'
                      : isDark
                      ? 'text-slate-400 hover:text-slate-200'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Share2 className="w-3.5 h-3.5 text-purple-500" /> Export Code
                </button>
              </div>
            </header>

            {/* Workspace Tab View Content */}
            <div className="flex-1 p-4 md:p-5 overflow-y-auto w-full">
              {activeTab === 'studio' && (
                <AIStudioView
                  layer={activeLayer}
                  theme={theme}
                  onMetricAddedToLibrary={handleAddMetricFromStudio}
                  onEditMetricRequest={handleEditSuggestion}
                />
              )}

              {activeTab === 'metrics' && (
                <MetricsCatalogView
                  metrics={activeLayer.metrics}
                  theme={theme}
                  onDeleteMetric={handleDeleteMetric}
                  onEditMetric={(m) => {
                    setEditingMetric(m);
                    setIsMetricModalOpen(true);
                  }}
                  onOpenStudio={() => setActiveTab('studio')}
                />
              )}

              {activeTab === 'export' && (
                <ExportPlaygroundView layer={activeLayer} theme={theme} />
              )}
            </div>
          </div>
        )}
      </main>

      {/* Modals */}
      <ConnectDbModal
        isOpen={isConnectModalOpen}
        onClose={() => setIsConnectModalOpen(false)}
        onSuccess={handleDbConnectedSuccess}
      />

      <SettingsModal
        isOpen={isSettingsModalOpen}
        onClose={() => setIsSettingsModalOpen(false)}
      />

      <MetricModal
        isOpen={isMetricModalOpen}
        onClose={() => setIsMetricModalOpen(false)}
        onSave={handleSaveMetric}
        initialMetric={editingMetric}
      />
    </div>
  );
}
