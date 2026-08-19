"use client";

import { useEffect, useState } from "react";

const testimonials = [
  {
    quote:
      "AI Agent tự động introspect schema metadata, đề xuất tên nghiệp vụ tiếng Việt và business metrics. HITL review giúp con người kiểm soát trước khi lưu.",
    author: "Semantic Layer Agent",
    role: "2-Pass AI Enrichment",
    company: "Flow 1",
    metric: "Schema introspection",
  },
  {
    quote:
      "SemanticQueryCompiler biên dịch metrics và dimensions thành câu SELECT. sqlglot AST validation đảm bảo chỉ cho phép read-only, auto-append LIMIT 100.",
    author: "Deterministic Compiler",
    role: "SELECT-only Guardrail",
    company: "Flow 2",
    metric: "An toàn tuyệt đối",
  },
  {
    quote:
      "Connection URLs được mã hóa Fernet trước khi lưu trữ. Statement timeout 15s ngăn chặn query quá lâu. Không bao giờ lưu plaintext.",
    author: "Security Layer",
    role: "Fernet Encryption",
    company: "Infrastructure",
    metric: "Zero plaintext",
  },
  {
    quote:
      "Xuất semantic layer definitions sang JSON hoặc YAML. Versioning và HITL review giúp duy trì tính nhất quán qua các thay đổi.",
    author: "Export Engine",
    role: "JSON / YAML Export",
    company: "Integration",
    metric: "Portable definitions",
  },
];

export function TestimonialsSection() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setIsAnimating(true);
      setTimeout(() => {
        setActiveIndex((prev) => (prev + 1) % testimonials.length);
        setIsAnimating(false);
      }, 300);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const activeTestimonial = testimonials[activeIndex];

  return (
    <section className="relative py-32 lg:py-40 border-t border-foreground/10 lg:pb-14">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        {/* Section Label */}
        <div className="flex items-center gap-4 mb-16">
          <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase">
            Phản hồi từ người dùng
          </span>
          <div className="flex-1 h-px bg-foreground/10" />
          <span className="font-mono text-xs text-muted-foreground">
            {String(activeIndex + 1).padStart(2, "0")} /{" "}
            {String(testimonials.length).padStart(2, "0")}
          </span>
        </div>

        {/* Main Quote */}
        <div className="grid lg:grid-cols-12 gap-12 lg:gap-20">
          <div className="lg:col-span-8">
            <blockquote
              className={`transition-all duration-300 ${
                isAnimating
                  ? "opacity-0 translate-y-4"
                  : "opacity-100 translate-y-0"
              }`}
            >
              <p className="font-display text-4xl md:text-5xl lg:text-6xl leading-[1.1] tracking-tight text-foreground">
                &ldquo;{activeTestimonial.quote}&rdquo;
              </p>
            </blockquote>

            {/* Author */}
            <div
              className={`mt-12 flex items-center gap-6 transition-all duration-300 delay-100 ${
                isAnimating ? "opacity-0" : "opacity-100"
              }`}
            >
              <div className="w-16 h-16 rounded-full bg-foreground/5 border border-foreground/10 flex items-center justify-center">
                <span className="font-display text-2xl text-foreground">
                  {activeTestimonial.author.charAt(0)}
                </span>
              </div>
              <div>
                <p className="text-lg font-medium text-foreground">
                  {activeTestimonial.author}
                </p>
                <p className="text-muted-foreground">
                  {activeTestimonial.role}, {activeTestimonial.company}
                </p>
              </div>
            </div>
          </div>

          {/* Metric Highlight */}
          <div className="lg:col-span-4 flex flex-col justify-center">
            <div
              className={`p-8 border border-foreground/10 transition-all duration-300 ${
                isAnimating
                  ? "opacity-0 scale-95"
                  : "opacity-100 scale-100"
              }`}
            >
              <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase block mb-4">
                Kết quả nổi bật
              </span>
              <p className="font-display text-3xl md:text-4xl text-foreground">
                {activeTestimonial.metric}
              </p>
            </div>

            {/* Navigation Dots */}
            <div className="flex gap-2 mt-8">
              {testimonials.map((_, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setIsAnimating(true);
                    setTimeout(() => {
                      setActiveIndex(idx);
                      setIsAnimating(false);
                    }, 300);
                  }}
                  className={`h-2 transition-all duration-300 ${
                    idx === activeIndex
                      ? "w-8 bg-foreground"
                      : "w-2 bg-foreground/20 hover:bg-foreground/40"
                  }`}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Capability Labels Marquee */}
        <div className="mt-24 pt-12 border-t border-foreground/10">
          <p className="font-mono text-xs tracking-widest text-muted-foreground uppercase mb-8 text-center">
            Các khả năng chính
          </p>
        </div>
      </div>

      {/* Full-width marquee outside container */}
      <div className="w-full">
        <div className="flex gap-16 items-center marquee">
          {[...Array(2)].map((_, setIdx) => (
            <div key={setIdx} className="flex gap-16 items-center shrink-0">
              {[
                "Schema Introspection",
                "AI Enrichment",
                "HITL Review",
                "Deterministic Compiler",
                "Fernet Encryption",
                "SELECT-only",
                "JSON Export",
                "YAML Export",
              ].map((item) => (
                <span
                  key={`${setIdx}-${item}`}
                  className="font-display text-xl md:text-2xl text-foreground/30 whitespace-nowrap hover:text-foreground transition-colors duration-300"
                >
                  {item}
                </span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
