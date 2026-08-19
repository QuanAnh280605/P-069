"use client";

import { useEffect, useState, useRef } from "react";
import { ArrowRight } from "lucide-react";

const steps = [
  {
    number: "01",
    title: "Kết nối Database",
    description:
      "Cung cấp connection string (Live DB) hoặc upload SQL Dump. Hệ thống tự động mã hóa và lưu trữ an toàn.",
    detail: "PostgreSQL, MySQL, SQLite",
  },
  {
    number: "02",
    title: "AI Introspect Schema",
    description:
      "AI Agent đọc metadata schema, phân tích bảng, cột, quan hệ. Đề xuất tên nghiệp vụ bằng tiếng Việt.",
    detail: "SQLAlchemy Inspector",
  },
  {
    number: "03",
    title: "HITL Review & Approve",
    description:
      "Data steward xem xét, chỉnh sửa và phê duyệt tên nghiệp vụ. Mỗi thay đổi đều có audit log.",
    detail: "Human-in-the-Loop",
  },
  {
    number: "04",
    title: "Define Metrics & Query",
    description:
      "Định nghĩa business metrics và dimensions. SemanticQueryCompiler biên dịch thành SQL chính xác trên Live DB. SQL Dump chỉ dùng để ingest schema metadata.",
    detail: "Read-Only, AST Validated",
  },
];

export function HowItWorksSection() {
  const [isVisible, setIsVisible] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setIsVisible(true);
      },
      { threshold: 0.1 }
    );

    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      id="how-it-works"
      ref={sectionRef}
      className="relative py-24 lg:py-32 bg-foreground/[0.02] overflow-hidden"
    >
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        {/* Header */}
        <div
          className={`text-center max-w-3xl mx-auto mb-16 lg:mb-24 transition-all duration-700 ${
            isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
        >
          <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
            <span className="w-8 h-px bg-foreground/30" />
            Cách hoạt động
            <span className="w-8 h-px bg-foreground/30" />
          </span>
          <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-6">
            Bốn bước
            <br />
            đến semantic layer.
          </h2>
          <p className="text-xl text-muted-foreground">
            Từ kết nối database đến truy vấn metrics, quy trình hoàn toàn tự
            động với con người phê duyệt.
          </p>
        </div>

        {/* Steps */}
        <div className="grid lg:grid-cols-4 gap-px bg-foreground/5">
          {steps.map((step, index) => (
            <div
              key={step.number}
              className={`group relative p-8 lg:p-10 bg-background cursor-pointer transition-all duration-500 ${
                activeStep === index
                  ? "bg-foreground/[0.03]"
                  : "hover:bg-foreground/[0.01]"
              } ${
                isVisible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-8"
              }`}
              style={{ transitionDelay: `${index * 100}ms` }}
              onMouseEnter={() => setActiveStep(index)}
            >
              {/* Step Number */}
              <span className="text-6xl font-display text-foreground/5 mb-4 block">
                {step.number}
              </span>

              {/* Content */}
              <h3 className="text-xl font-medium mb-3 group-hover:translate-x-1 transition-transform duration-300">
                {step.title}
              </h3>
              <p className="text-muted-foreground leading-relaxed mb-4">
                {step.description}
              </p>

              {/* Detail Badge */}
              <span className="inline-flex items-center gap-2 text-xs font-mono text-muted-foreground border border-foreground/10 px-3 py-1.5">
                {step.detail}
                <ArrowRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
              </span>

              {/* Active Indicator */}
              <div
                className={`absolute bottom-0 left-0 right-0 h-0.5 bg-foreground transition-all duration-500 ${
                  activeStep === index ? "opacity-100" : "opacity-0"
                }`}
              />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
