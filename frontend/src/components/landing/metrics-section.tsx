"use client";

import { useEffect, useState, useRef } from "react";

const metrics = [
  {
    value: "2-pass",
    label: "AI Enrichment",
    description: "Làm giàu schema metadata",
  },
  {
    value: "SELECT",
    label: "Only",
    description: "Deterministic compiler",
  },
  {
    value: "<15s",
    label: "Query timeout",
    description: "Bảo vệ hiệu năng",
  },
  {
    value: "100%",
    label: "Read-only",
    description: "An toàn tuyệt đối",
  },
];

export function MetricsSection() {
  const [isVisible, setIsVisible] = useState(false);
  const [countedValues, setCountedValues] = useState<string[]>(
    metrics.map(() => "0")
  );
  const sectionRef = useRef<HTMLElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          setIsVisible(true);
          hasAnimated.current = true;
          // Animate count-up
          const duration = 1500;
          const startTime = Date.now();
          const targetValues = metrics.map((m) => m.value);

          const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);

            setCountedValues(
              targetValues.map((target) => {
                const numMatch = target.match(/[\d.]+/);
                if (!numMatch) return target;
                const num = parseFloat(numMatch[0]);
                const current = Math.floor(num * eased);
                return target.replace(numMatch[0], String(current));
              })
            );

            if (progress < 1) requestAnimationFrame(animate);
            else setCountedValues(targetValues);
          };
          requestAnimationFrame(animate);
        }
      },
      { threshold: 0.2 }
    );

    if (sectionRef.current) observer.observe(sectionRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      ref={sectionRef}
      className="relative py-24 lg:py-32 border-t border-foreground/10"
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
            Hiệu suất
            <span className="w-8 h-px bg-foreground/30" />
          </span>
          <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-6">
            Số liệu nói
            <br />
            lên tất cả.
          </h2>
        </div>

        {/* Metrics Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-px bg-foreground/5">
          {metrics.map((metric, index) => (
            <div
              key={metric.label}
              className={`group p-8 lg:p-12 bg-background text-center transition-all duration-500 hover:bg-foreground/[0.02] ${
                isVisible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-8"
              }`}
              style={{ transitionDelay: `${index * 100}ms` }}
            >
              <span className="block font-display text-5xl lg:text-6xl text-foreground mb-2">
                {countedValues[index]}
              </span>
              <span className="block text-lg font-medium mb-1">
                {metric.label}
              </span>
              <span className="block text-sm text-muted-foreground">
                {metric.description}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
