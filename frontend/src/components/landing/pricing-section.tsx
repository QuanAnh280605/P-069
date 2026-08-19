"use client";

import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";

const betaFeatures = [
  "Kết nối PostgreSQL, MySQL, SQLite",
  "Ingest SQL Dump schema metadata",
  "2-Pass AI enrichment với HITL review",
  "Deterministic SemanticQueryCompiler",
  "SELECT-only guardrails, LIMIT 100",
  "Fernet encrypted connection storage",
  "Export JSON / YAML",
  "Versioning & audit trail",
];

export function PricingSection() {
  return (
    <section
      id="pricing"
      className="relative py-32 lg:py-40 border-t border-foreground/10"
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        {/* Header */}
        <div className="max-w-3xl mb-20">
          <span className="font-mono text-xs tracking-widest text-muted-foreground uppercase block mb-6">
            Beta
          </span>
          <h2 className="font-display text-5xl md:text-6xl lg:text-7xl tracking-tight text-foreground mb-6">
            Sẵn sàng
            <br />
            <span className="text-stroke">sử dụng.</span>
          </h2>
          <p className="text-lg text-muted-foreground max-w-xl">
            Semantic Layer Agent hiện đang trong giai đoạn beta. Tất cả tính năng
            cốt lõi đều sẵn sàng sử dụng miễn phí.
          </p>
        </div>

        {/* Beta Card */}
        <div className="max-w-2xl">
          <div className="p-8 lg:p-12 bg-background border-2 border-foreground">
            <span className="absolute -top-3 left-8 px-3 py-1 bg-foreground text-primary-foreground text-xs font-mono uppercase tracking-widest">
              Beta
            </span>

            <div className="mb-8">
              <h3 className="font-display text-3xl text-foreground mt-2">
                Miễn phí
              </h3>
              <p className="text-sm text-muted-foreground mt-2">
                Tất cả tính năng cốt lõi đều sẵn sàng trong giai đoạn beta.
              </p>
            </div>

            <div className="mb-8 pb-8 border-b border-foreground/10">
              <div className="flex items-baseline gap-2">
                <span className="font-display text-5xl lg:text-6xl text-foreground">
                  0₫
                </span>
                <span className="text-muted-foreground">/tháng</span>
              </div>
            </div>

            <ul className="space-y-4 mb-10">
              {betaFeatures.map((feature) => (
                <li key={feature} className="flex items-start gap-3">
                  <Check className="w-4 h-4 text-foreground mt-0.5 shrink-0" />
                  <span className="text-sm text-muted-foreground">
                    {feature}
                  </span>
                </li>
              ))}
            </ul>

            <Link
              href="/register"
              className="w-full py-4 flex items-center justify-center gap-2 text-sm font-medium bg-foreground text-primary-foreground hover:bg-foreground/90 transition-all group"
            >
              Bắt đầu miễn phí
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </div>

        {/* Bottom Note */}
        <p className="mt-12 text-sm text-muted-foreground max-w-2xl">
          Tất cả bao gồm mã hóa Fernet, audit log, và bảo mật Read-Only.
          Chỉ hỗ trợ SELECT statements, không cho phép thay đổi dữ liệu.
        </p>
      </div>
    </section>
  );
}
