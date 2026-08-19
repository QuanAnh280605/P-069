"use client";

import { useEffect, useState, useRef } from "react";
import { AnimatedSphere } from "./animated-sphere";
import { AnimatedTetrahedron } from "./animated-tetrahedron";
import { AnimatedWave } from "./animated-wave";

export function InfrastructureSection() {
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
            Hạ tầng
            <span className="w-8 h-px bg-foreground/30" />
          </span>
          <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-6">
            Xây dựng trên
            <br />
            nền tảng vững chắc.
          </h2>
          <p className="text-xl text-muted-foreground">
            Kiến trúc bảo mật đa lớp, mã hóa end-to-end, và guardrails ngăn
            chặn mọi truy vấn nguy hiểm.
          </p>
        </div>

        {/* ASCII Animation Showcase */}
        <div className="grid lg:grid-cols-3 gap-8">
          {[
            {
              Component: AnimatedSphere,
              label: "Schema Introspection",
              desc: "Đọc metadata 360°",
            },
            {
              Component: AnimatedTetrahedron,
              label: "Query Compilation",
              desc: "Biên dịch chính xác",
            },
            {
              Component: AnimatedWave,
              label: "Export & Integration",
              desc: "JSON / YAML export",
            },
          ].map(({ Component, label, desc }, index) => (
            <div
              key={label}
              className={`group relative border border-foreground/10 hover:border-foreground/20 transition-all duration-500 ${
                isVisible
                  ? "opacity-100 translate-y-0"
                  : "opacity-0 translate-y-8"
              }`}
              style={{ transitionDelay: `${index * 150}ms` }}
            >
              <div className="aspect-square bg-foreground/[0.01] flex items-center justify-center p-2 overflow-hidden">
                <Component />
              </div>
              <div className="p-6 border-t border-foreground/10">
                <h3 className="font-medium mb-1 group-hover:translate-x-1 transition-transform">
                  {label}
                </h3>
                <p className="text-sm text-muted-foreground">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
