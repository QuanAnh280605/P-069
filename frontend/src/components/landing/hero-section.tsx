"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AnimatedSphere } from "./animated-sphere";

const words = ["chuẩn hóa", "định nghĩa", "truy vấn", "quản trị"];

export function HeroSection() {
  const [isVisible, setIsVisible] = useState(false);
  const [wordIndex, setWordIndex] = useState(0);

  useEffect(() => {
    setIsVisible(true);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setWordIndex((prev) => (prev + 1) % words.length);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="relative min-h-screen flex flex-col justify-center overflow-hidden">
      {/* Animated sphere background - Full scale like Optimus without clipping or obscuring overlays */}
      <div className="absolute right-[-5%] lg:right-0 top-1/2 -translate-y-1/2 w-[650px] h-[650px] lg:w-[850px] lg:h-[850px] xl:w-[1000px] xl:h-[1000px] opacity-45 pointer-events-none">
        <AnimatedSphere />
      </div>

      {/* Subtle grid lines */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-30">
        {[...Array(8)].map((_, i) => (
          <div
            key={`h-${i}`}
            className="absolute h-px bg-foreground/10"
            style={{
              top: `${12.5 * (i + 1)}%`,
              left: 0,
              right: 0,
            }}
          />
        ))}
        {[...Array(12)].map((_, i) => (
          <div
            key={`v-${i}`}
            className="absolute w-px bg-foreground/10"
            style={{
              left: `${8.33 * (i + 1)}%`,
              top: 0,
              bottom: 0,
            }}
          />
        ))}
      </div>

      <div className="relative z-10 max-w-[1400px] mx-auto px-6 lg:px-12 py-32 lg:py-40">
        {/* Eyebrow */}
        <div
          className={`mb-8 transition-all duration-700 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
        >
          <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground">
            <span className="w-8 h-px bg-foreground/30" />
            Nền tảng AI Semantic Layer Agent
          </span>
        </div>

        {/* Main headline */}
        <div className="mb-12">
          <h1
            className={`text-[clamp(3rem,12vw,10rem)] font-display leading-[0.9] tracking-tight transition-all duration-1000 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
          >
            <span className="block">Nền tảng</span>
            <span className="block">
              để{" "}
              <span className="relative inline-block">
                <span key={wordIndex} className="inline-flex">
                  {words[wordIndex].split("").map((char, i) => (
                    <span
                      key={`${wordIndex}-${i}`}
                      className="inline-block animate-char-in"
                      style={{
                        animationDelay: `${i * 50}ms`,
                      }}
                    >
                      {char === " " ? "\u00A0" : char}
                    </span>
                  ))}
                </span>
                <span className="absolute -bottom-2 left-0 right-0 h-3 bg-foreground/10" />
              </span>
            </span>
          </h1>
        </div>

        {/* Description */}
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-24 items-end">
          <p
            className={`text-xl lg:text-2xl text-muted-foreground leading-relaxed max-w-xl transition-all duration-700 delay-200 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
              }`}
          >
            Tự động chuyển đổi DB schema kỹ thuật thành ngôn ngữ nghiệp vụ thống nhất.
            Xây dựng, quản trị và biên dịch chỉ số.
          </p>

          {/* CTAs */}
          <div
            className={`flex flex-col sm:flex-row items-start gap-4 transition-all duration-700 delay-300 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
              }`}
          >
            <Button
              asChild
              size="lg"
              className="bg-foreground hover:bg-foreground/90 text-background px-8 h-14 text-base rounded-full group cursor-pointer"
            >
              <Link href="/register">
                Dùng thử miễn phí
                <ArrowRight className="w-4 h-4 ml-2 transition-transform group-hover:translate-x-1" />
              </Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="h-14 px-8 text-base rounded-full border-foreground/20 hover:bg-foreground/5 cursor-pointer"
            >
              <Link href="/login">
                <Play className="w-4 h-4 mr-2" />
                Đăng nhập
              </Link>
            </Button>
          </div>
        </div>
      </div>

      {/* Stats marquee - full width outside container */}
      <div
        className={`absolute bottom-16 lg:bottom-20 left-0 right-0 transition-all duration-700 delay-500 ${isVisible ? "opacity-100" : "opacity-0"
          }`}
      >
        <div className="flex gap-16 marquee whitespace-nowrap">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="flex gap-16">
              {[
                { value: "100%", label: "An toàn dữ liệu", company: "GUARDRAIL" },
                { value: "<15s", label: "Giới hạn truy vấn", company: "TIMEOUT" },
                { value: "2-Pass", label: "Làm giàu ngữ nghĩa", company: "LLM ENRICH" },
                { value: "0%", label: "Sai lệch chỉ số", company: "ZERO HALLUCINATION" },
              ].map((stat) => (
                <div key={`${stat.company}-${i}`} className="flex items-baseline gap-4">
                  <span className="text-4xl lg:text-5xl font-display">{stat.value}</span>
                  <span className="text-sm text-muted-foreground">
                    {stat.label}
                    <span className="block font-mono text-xs mt-1">{stat.company}</span>
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
