"use client";

import { useEffect, useState, useRef } from "react";
import {
  Database,
  GitBranch,
  Zap,
  Shield,
  BarChart3,
  FileCode,
} from "lucide-react";

const features = [
  {
    icon: Database,
    title: "Introspect Schema",
    description:
      "Tự động đọc metadata schema thông qua SQLAlchemy Inspector. Hỗ trợ Live DB và SQL Dump (chỉ ingest metadata, không truy vấn dữ liệu).",
    tag: "Flow 1",
    span: "lg:col-span-2 lg:row-span-2",
  },
  {
    icon: GitBranch,
    title: "HITL Workflow",
    description:
      "Con người duyệt và phê duyệt tên nghiệp vụ do AI đề xuất trước khi lưu vào semantic layer.",
    tag: "Governance",
    span: "",
  },
  {
    icon: Zap,
    title: "Biên dịch Metrics",
    description:
      "SemanticQueryCompiler chuyển đổi metrics và dimensions thành SQL chính xác trên Live DB. Không dùng Text-to-SQL tự do.",
    tag: "Flow 2 — Live DB",
    span: "",
  },
  {
    icon: Shield,
    title: "Read-Only Guardrails",
    description:
      "Chỉ cho phép SELECT. AST validation, auto-append LIMIT 100, statement timeout 15 giây.",
    tag: "Bảo mật",
    span: "lg:col-span-2",
  },
  {
    icon: BarChart3,
    title: "Business Metrics",
    description:
      "Định nghĩa chỉ số thống nhất: revenue, churn rate, conversion. AI gợi ý tên tiếng Việt chuẩn nghiệp vụ.",
    tag: "Metrics",
    span: "",
  },
  {
    icon: FileCode,
    title: "Export Semantic",
    description:
      "Xuất semantic layer definitions sang JSON và YAML.",
    tag: "Export",
    span: "",
  },
];

export function BentoFeaturesSection() {
  const [isVisible, setIsVisible] = useState(false);
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
      id="features"
      ref={sectionRef}
      className="relative py-24 lg:py-32 overflow-hidden"
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
            Tính năng
            <span className="w-8 h-px bg-foreground/30" />
          </span>
          <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-6">
            Mọi thứ bạn cần
            <br />
            để quản trị dữ liệu.
          </h2>
          <p className="text-xl text-muted-foreground">
            Từ introspect schema đến biên dịch metrics, tất cả trong một nền
            tảng duy nhất.
          </p>
        </div>

        {/* Bento Grid */}
        <div className="grid lg:grid-cols-4 gap-px bg-foreground/5">
          {features.map((feature, index) => (
            <div
              key={feature.title}
              className={`group relative p-8 lg:p-10 bg-background hover:bg-foreground/[0.02] transition-all duration-500 ${
                feature.span
              } ${
                isVisible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-8"
              }`}
              style={{ transitionDelay: `${index * 100}ms` }}
            >
              {/* Tag */}
              <span className="inline-block text-xs font-mono text-muted-foreground border border-foreground/10 px-2 py-1 mb-6">
                {feature.tag}
              </span>

              {/* Icon */}
              <div className="w-12 h-12 flex items-center justify-center border border-foreground/10 mb-6 group-hover:bg-foreground group-hover:text-background transition-colors duration-300">
                <feature.icon className="w-6 h-6" />
              </div>

              {/* Content */}
              <h3 className="text-xl font-medium mb-3 group-hover:translate-x-1 transition-transform duration-300">
                {feature.title}
              </h3>
              <p className="text-muted-foreground leading-relaxed">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
