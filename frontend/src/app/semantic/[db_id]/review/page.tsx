'use client';

import React, { useState, useEffect, use } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  getLayerById,
  updateLayer,
  SemanticLayerData,
  BusinessMetric,
  MetricSuggestion,
  deleteMetricApi,
} from '@/lib/api';
import { MetricModal } from '@/components/modals/MetricModal';
import { CubeSidebar, CubeNavTab } from '@/components/layout/CubeSidebar';
import { CubeTopBar } from '@/components/layout/CubeTopBar';
import { AIStudioView } from '@/components/views/AIStudioView';
import { DataModelView } from '@/components/views/DataModelView';
import { MetricsCatalogView } from '@/components/views/MetricsCatalogView';
import { ExportPlaygroundView } from '@/components/views/ExportPlaygroundView';
import { Database, CheckCircle2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

export default function ReviewPage({ params }: { params: Promise<{ db_id: string }> }) {
  const resolvedParams = use(params);
  const router = useRouter();
  const { user, isLoading, logout } = useAuth();
  const [layer, setLayer] = useState<SemanticLayerData | null>(null);

  // Cube Navigation State: 'studio' (Màn hình 2) | 'tables' | 'metrics' | 'export'
  const [activeTab, setActiveTab] = useState<CubeNavTab>('studio');

  // Theme State: 'light' (Warm Minimalist default) | 'dark' (Deep Slate)
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  // Modal State for fine-tuning individual metrics
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingMetric, setEditingMetric] = useState<BusinessMetric | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    const data = getLayerById(resolvedParams.db_id);
    if (data) {
      setLayer(data);
    }
    const savedTheme = localStorage.getItem('cube_theme') as 'light' | 'dark';
    if (savedTheme) {
      setTheme(savedTheme);
    }
  }, [resolvedParams.db_id]);

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    localStorage.setItem('cube_theme', nextTheme);
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  if (!user && !isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-[#0B0F19]">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-10 text-center max-w-lg mx-auto shadow-2xl">
          <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 text-indigo-400 flex items-center justify-center mx-auto mb-4 border border-indigo-500/30">
            <Database className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Yêu cầu Đăng nhập</h2>
          <p className="text-xs text-slate-400 mb-6">
            Vui lòng đăng nhập để truy cập Cube Semantic Layer & AI Metric Studio.
          </p>
          <Link href="/login" className="gradient-btn px-6 py-2.5 text-xs font-bold text-white rounded-xl inline-block shadow-lg">
            Đăng nhập ngay (JWT / Google)
          </Link>
        </div>
      </div>
    );
  }

  if (!layer) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0B0F19] text-center p-6 text-slate-400">
        <div>
          <Database className="w-12 h-12 mx-auto text-slate-600 mb-3" />
          <p className="text-sm font-semibold">Không tìm thấy thông tin Semantic Layer</p>
          <Link href="/" className="text-indigo-400 font-semibold underline text-xs mt-2 inline-block">
            ← Quay lại Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const handleSaveOfficial = () => {
    if (!layer) return;
    const updated: SemanticLayerData = {
      ...layer,
      status: 'Saved',
      updated_at: new Date().toISOString().replace('T', ' ').slice(0, 16),
    };
    updateLayer(updated);
    setLayer(updated);
    showToast('🎉 Đã lưu Semantic Layer thành công vào trạng thái Production!');
  };

  const handleSaveMetric = (savedMetric: BusinessMetric) => {
    if (!layer) return;
    const existingIdx = layer.metrics.findIndex((m) => m.id === savedMetric.id);
    let updatedMetrics = [...layer.metrics];
    if (existingIdx >= 0) {
      updatedMetrics[existingIdx] = savedMetric;
    } else {
      updatedMetrics = [...layer.metrics, savedMetric];
    }
    const updatedLayer = { ...layer, metrics: updatedMetrics, status: 'Draft' as const };
    setLayer(updatedLayer);
    updateLayer(updatedLayer);
    setIsModalOpen(false);
    showToast(`✅ Đã cập nhật chỉ số "${savedMetric.name}"!`);
  };

  const handleDeleteMetric = async (mId: string) => {
    await deleteMetricApi(layer.id, mId);
    const updatedMetrics = layer.metrics.filter((m) => m.id !== mId);
    const updatedLayer = { ...layer, metrics: updatedMetrics, status: 'Draft' as const };
    setLayer(updatedLayer);
    updateLayer(updatedLayer);
    showToast('🗑️ Đã xóa chỉ số khỏi thư viện.');
  };

  const handleAddMetricFromStudio = (newMetric: MetricSuggestion) => {
    const localMetric: BusinessMetric = {
      id: `m_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      name: newMetric.name,
      description: newMetric.description,
      sql_template: newMetric.sql_template,
      source: 'ai',
      created_at: new Date().toISOString(),
    };
    const updatedMetrics = [...layer.metrics, localMetric];
    const updatedLayer = { ...layer, metrics: updatedMetrics, status: 'Draft' as const };
    setLayer(updatedLayer);
    updateLayer(updatedLayer);
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
    setIsModalOpen(true);
  };

  const handleEditMetricFromCatalog = (metric: BusinessMetric) => {
    setEditingMetric(metric);
    setIsModalOpen(true);
  };

  return (
    <div
      className={`min-h-screen flex transition-colors duration-150 ${
        theme === 'light' ? 'bg-[#FAF9F6] text-slate-900' : 'bg-[#0B0F19] text-slate-100'
      }`}
    >
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-6 right-6 z-60 bg-slate-900 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow-xl border border-slate-700 animate-in slide-in-from-top flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Left Contrast Dark Sidebar (Cube.dev Style) */}
      <CubeSidebar
        activeTab={activeTab}
        onTabChange={(tab) => setActiveTab(tab)}
        theme={theme}
        dbName={layer.db_name}
        dbType={layer.db_type}
        metricCount={layer.metrics.length}
        tableCount={layer.tables.length}
        user={user}
        onLogout={logout}
      />

      {/* Main App Workspace Canvas - 100% Edge-to-Edge */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Top Control Bar with Breadcrumbs & Theme Switcher */}
        <CubeTopBar
          dbName={layer.db_name}
          status={layer.status}
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
          onSaveOfficial={handleSaveOfficial}
          theme={theme}
          onToggleTheme={toggleTheme}
        />

        {/* View Content Area - Full Responsive Canvas */}
        <main className="flex-1 p-4 md:p-5 overflow-y-auto w-full max-w-none">
          {/* Màn hình 2: AI Metric Studio (Mặc định) */}
          {activeTab === 'studio' && (
            <AIStudioView
              layer={layer}
              theme={theme}
              onMetricAddedToLibrary={handleAddMetricFromStudio}
              onEditMetricRequest={handleEditSuggestion}
            />
          )}

          {/* Màn hình 1: Data Modeling & Schema Explorer */}
          {activeTab === 'tables' && (
            <DataModelView
              layer={layer}
              theme={theme}
              onOpenStudioForTable={() => setActiveTab('studio')}
            />
          )}

          {/* Màn hình 3: Business Metrics Catalog */}
          {activeTab === 'metrics' && (
            <MetricsCatalogView
              metrics={layer.metrics}
              theme={theme}
              onDeleteMetric={handleDeleteMetric}
              onEditMetric={handleEditMetricFromCatalog}
              onOpenStudio={() => setActiveTab('studio')}
            />
          )}

          {/* Màn hình 4: Semantic Export & Integrations */}
          {activeTab === 'export' && (
            <ExportPlaygroundView layer={layer} theme={theme} />
          )}
        </main>
      </div>

      {/* Detailed Edit Modal */}
      <MetricModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveMetric}
        initialMetric={editingMetric}
      />
    </div>
  );
}
