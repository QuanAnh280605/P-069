'use client';

import { CheckCircle2, ChevronDown, ChevronRight, Code2, Loader2, Sparkles, X } from 'lucide-react';
import React, { useEffect, useState } from 'react';

import { SqlCodeViewer } from '@/components/studio/SqlCodeViewer';
import {
  advanceWizardApi,
  SemanticQuerySpec,
  startWizardApi,
  WizardOption,
  WizardStepResponse,
} from '@/lib/api';

interface Props {
  isOpen: boolean;
  dbId: number;
  theme: 'light' | 'dark';
  onClose: () => void;
  onResolved: (spec: SemanticQuerySpec) => void;
}

export function AIQueryModal({ isOpen, dbId, theme, onClose, onResolved }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [step, setStep] = useState<number>(1);
  const [title, setTitle] = useState<string>('');
  const [question, setQuestion] = useState<string>('');
  const [options, setOptions] = useState<WizardOption[]>([]);
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const [resolvedSpec, setResolvedSpec] = useState<SemanticQuerySpec | null>(null);
  const [sqlPreview, setSqlPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [showSql, setShowSql] = useState<boolean>(false);

  const isDark = theme === 'dark';

  const resetModalState = () => {
    setSessionId(null);
    setStep(1);
    setTitle('');
    setQuestion('');
    setOptions([]);
    setSelectedOptionId(null);
    setIsCompleted(false);
    setResolvedSpec(null);
    setSqlPreview(null);
    setLoading(false);
    setError('');
    setShowSql(false);
  };

  const initWizard = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await startWizardApi(dbId);
      setSessionId(res.session_id);
      setStep(res.step);
      setTitle(res.title);
      setQuestion(res.question);
      setOptions(res.options);
      setIsCompleted(res.is_completed);
      if (res.options.length > 0) {
        setSelectedOptionId(res.options[0].id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không thể khởi tạo AI Query Assistant.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && dbId) {
      void initWizard();
    } else {
      resetModalState();
    }
  }, [isOpen, dbId]);

  const handleNextStep = async () => {
    if (!sessionId || !selectedOptionId) return;
    setLoading(true);
    setError('');
    try {
      const res: WizardStepResponse = await advanceWizardApi(dbId, sessionId, selectedOptionId);
      setStep(res.step);
      setTitle(res.title);
      setQuestion(res.question);
      setOptions(res.options);
      setIsCompleted(res.is_completed);

      if (res.options.length > 0) {
        setSelectedOptionId(res.options[0].id);
      }

      if (res.is_completed) {
        setResolvedSpec(res.resolved_spec || null);
        setSqlPreview(res.sql_preview || null);
      }
    } catch (err: any) {
      setError(err?.message || 'Có lỗi xảy ra trong quá trình xử lý.');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    if (resolvedSpec) {
      onResolved(resolvedSpec);
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div
        className={`w-full max-w-2xl rounded-xl shadow-2xl border transition-colors ${
          isDark ? 'bg-slate-900 border-slate-800 text-slate-100' : 'bg-white border-slate-200 text-slate-900'
        }`}
      >
        {/* Header */}
        <div
          className={`flex items-center justify-between px-6 py-4 border-b ${
            isDark ? 'border-slate-800' : 'border-slate-200'
          }`}
        >
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-600/10 text-indigo-600">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-semibold text-lg">{title || 'AI Query Assistant Wizard'}</h3>
              <p className="text-xs text-slate-500">Định nghĩa truy vấn qua Radio Buttons</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className={`p-1.5 rounded-lg transition-colors ${
              isDark ? 'hover:bg-slate-800 text-slate-400' : 'hover:bg-slate-100 text-slate-500'
            }`}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Step Indicator */}
        <div
          className={`flex items-center justify-around px-6 py-3 border-b text-xs font-medium ${
            isDark ? 'bg-slate-950/50 border-slate-800 text-slate-400' : 'bg-slate-50 border-slate-200 text-slate-600'
          }`}
        >
          <span className={step === 1 ? 'text-indigo-600 font-bold' : ''}>1. Chọn Chỉ Số</span>
          <span>&rarr;</span>
          <span className={step === 2 ? 'text-indigo-600 font-bold' : ''}>2. Chọn Chiều Phân Tích</span>
          <span>&rarr;</span>
          <span className={step === 3 ? 'text-indigo-600 font-bold' : ''}>3. Xem Trước & Áp Dụng</span>
        </div>

        {/* Body */}
        <div className="p-6 max-h-[60vh] overflow-y-auto space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-600 text-sm">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
              <p className="text-sm text-slate-500">Đang khởi tạo hướng dẫn từ Semantic Layer...</p>
            </div>
          ) : !isCompleted ? (
            <div className="space-y-4">
              <p className="font-medium text-base">{question}</p>
              <div className="space-y-2">
                {options.map((opt) => {
                  const isSelected = selectedOptionId === opt.id;
                  return (
                    <div
                      key={opt.id}
                      onClick={() => setSelectedOptionId(opt.id)}
                      className={`flex items-start gap-3 p-3.5 rounded-lg border cursor-pointer transition-all ${
                        isSelected
                          ? isDark
                            ? 'border-indigo-500 bg-indigo-950/20'
                            : 'border-indigo-600 bg-indigo-50/50'
                          : isDark
                          ? 'border-slate-800 bg-slate-900/50 hover:border-slate-700'
                          : 'border-slate-200 bg-white hover:border-slate-300'
                      }`}
                    >
                      <input
                        type="radio"
                        name="wizard-option"
                        checked={isSelected}
                        onChange={() => setSelectedOptionId(opt.id)}
                        className="mt-0.5 accent-indigo-600"
                      />
                      <div className="flex-1">
                        <div className="font-medium text-sm">{opt.label}</div>
                        {opt.description && (
                          <div className="text-xs text-slate-500 mt-0.5">{opt.description}</div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-emerald-600 font-medium">
                <CheckCircle2 className="w-5 h-5" />
                <span>Cấu hình truy vấn đã sẵn sàng!</span>
              </div>
              <p className="text-sm text-slate-500">
                Các thông số đã được tổng hợp từ lựa chọn của bạn. Hãy nhấn nút bên dưới để điền trực tiếp vào bộ điều khiển Explorer.
              </p>

              {sqlPreview && (
                <div className={`rounded-lg border overflow-hidden ${isDark ? 'border-slate-800' : 'border-slate-200'}`}>
                  <button
                    onClick={() => setShowSql(!showSql)}
                    className={`w-full flex items-center justify-between p-3 text-xs font-semibold ${
                      isDark ? 'bg-slate-800/50 text-slate-300' : 'bg-slate-100 text-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Code2 className="w-4 h-4 text-indigo-600" />
                      <span>Xem trước câu lệnh SQL compiled</span>
                    </div>
                    {showSql ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </button>
                  {showSql && (
                    <div className="p-3 bg-slate-950 text-slate-100 font-mono text-xs overflow-x-auto">
                      <SqlCodeViewer sql={sqlPreview} />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className={`flex items-center justify-end gap-3 px-6 py-4 border-t ${
            isDark ? 'border-slate-800 bg-slate-900/50' : 'border-slate-200 bg-slate-50'
          }`}
        >
          <button
            onClick={onClose}
            className={`px-4 py-2 text-sm font-medium rounded-lg border transition-colors ${
              isDark
                ? 'border-slate-700 hover:bg-slate-800 text-slate-300'
                : 'border-slate-300 hover:bg-slate-100 text-slate-700'
            }`}
          >
            Hủy
          </button>
          {!isCompleted ? (
            <button
              disabled={!selectedOptionId || loading}
              onClick={handleNextStep}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50 transition-colors shadow-sm"
            >
              {step === 1 ? 'Tiếp theo' : 'Xác nhận & Biên dịch'}
            </button>
          ) : (
            <button
              onClick={handleApply}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white transition-colors shadow-sm"
            >
              Áp dụng vào Explorer
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
