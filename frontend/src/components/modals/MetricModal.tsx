'use client';

import React, { useState, useEffect } from 'react';
import { X, Save, Code, Sparkles } from 'lucide-react';
import { BusinessMetric } from '@/lib/api';

interface MetricModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (metric: BusinessMetric) => void;
  initialMetric?: BusinessMetric | null;
}

export const MetricModal: React.FC<MetricModalProps> = ({
  isOpen,
  onClose,
  onSave,
  initialMetric,
}) => {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [sqlTemplate, setSqlTemplate] = useState('');

  useEffect(() => {
    if (initialMetric) {
      setName(initialMetric.name);
      setDescription(initialMetric.description);
      setSqlTemplate(initialMetric.sql_template);
    } else {
      setName('');
      setDescription('');
      setSqlTemplate('');
    }
  }, [initialMetric, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    const metric: BusinessMetric = {
      id: initialMetric ? initialMetric.id : `m_${Date.now()}`,
      name: name.trim(),
      description: description.trim(),
      sql_template: sqlTemplate.trim(),
      source: initialMetric ? initialMetric.source : 'manual',
      created_at: new Date().toISOString(),
    };

    onSave(metric);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-sm animate-in fade-in">
      <div className="glass-card w-full max-w-2xl rounded-2xl border border-indigo-500/30 shadow-2xl overflow-hidden bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50 dark:bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 dark:bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 flex items-center justify-center border border-emerald-200 dark:border-emerald-500/30">
              <Sparkles className="w-4 h-4" />
            </div>
            <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
              {initialMetric ? '✏️ SỬA BUSINESS METRIC' : '➕ THÊM BUSINESS METRIC THỦ CÔNG'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 dark:hover:text-white p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">
              Tên Metric
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Tỷ lệ đơn hàng hoàn thành (Completion Rate)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-slate-50 dark:bg-slate-900/90 border border-slate-300 dark:border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-slate-400 dark:placeholder:text-slate-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">
              Mô tả nghiệp vụ
            </label>
            <textarea
              rows={2}
              placeholder="e.g. % đơn hàng có status COMPLETED trên tổng số đơn hàng"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-slate-50 dark:bg-slate-900/90 border border-slate-300 dark:border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-slate-400 dark:placeholder:text-slate-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Code className="w-3.5 h-3.5 text-indigo-500 dark:text-indigo-400" /> SQL Template (tham chiếu)
            </label>
            <textarea
              rows={4}
              placeholder="SELECT ROUND(COUNT(*) FILTER(WHERE order_status = 'COMPLETED') * 100.0 / COUNT(*), 2) AS completion_rate FROM orders"
              value={sqlTemplate}
              onChange={(e) => setSqlTemplate(e.target.value)}
              className="w-full bg-slate-900 text-emerald-400 dark:bg-slate-950 font-mono text-xs rounded-xl p-4 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all placeholder:text-slate-600 leading-relaxed"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200 dark:border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
            >
              Hủy bỏ
            </button>
            <button
              type="submit"
              className="gradient-btn px-5 py-2 text-xs font-semibold text-white rounded-xl shadow-lg flex items-center gap-1.5 cursor-pointer"
            >
              <Save className="w-3.5 h-3.5" /> Lưu Metric
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
