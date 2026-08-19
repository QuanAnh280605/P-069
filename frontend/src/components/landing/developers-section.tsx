"use client";

import { useState, useEffect, useRef } from "react";
import { Copy, Check } from "lucide-react";

const codeExamples = [
  {
    label: "Kết nối",
    code: `from semantic_layer import SemanticClient

client = SemanticClient(
    connection="postgresql://...",
    encrypt=True  # Fernet AES-256
)

schema = client.introspect()
print(f"Found {len(schema.tables)} tables")`,
  },
  {
    label: "Truy vấn",
    code: `from semantic_layer import SemanticQueryCompiler

compiler = SemanticQueryCompiler(schema)

result = compiler.query(
    metrics=["doanh_thu", "ty_le_churn"],
    dimensions=["khu_vuc", "thang"],
    filters={"thang": "2025-01"}
)

# Auto-limited to 100 rows, SELECT-only`,
  },
  {
    label: "Xuất",
    code: `# Export semantic layer definitions
client.export(
    format="json",  # or yaml
    include_metrics=True,
    include_dimensions=True,
    output="./semantic_layer.json"
)`,
  },
];

const features = [
  {
    title: "Python native",
    description: "Type hints đầy đủ, async/await support.",
  },
  {
    title: "Zero config",
    description: "Kết nối và introspect ngay lập tức.",
  },
  {
    title: "Multi-DB",
    description: "PostgreSQL, MySQL, SQLite.",
  },
  {
    title: "2-Pass AI",
    description: "Làm giàu schema metadata tự động.",
  },
];

const codeAnimationStyles = `
  .dev-code-line {
    opacity: 0;
    transform: translateX(-8px);
    animation: devLineReveal 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  
  @keyframes devLineReveal {
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
  
  .dev-code-char {
    opacity: 0;
    filter: blur(8px);
    animation: devCharReveal 0.3s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }
  
  @keyframes devCharReveal {
    to {
      opacity: 1;
      filter: blur(0);
    }
  }
`;

export function DevelopersSection() {
  const [activeTab, setActiveTab] = useState(0);
  const [copied, setCopied] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);

  const handleCopy = () => {
    navigator.clipboard.writeText(codeExamples[activeTab].code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
      id="developers"
      ref={sectionRef}
      className="relative py-24 lg:py-32 overflow-hidden"
    >
      <style dangerouslySetInnerHTML={{ __html: codeAnimationStyles }} />
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid lg:grid-cols-2 gap-16 lg:gap-24 items-start">
          {/* Left: Content */}
          <div
            className={`transition-all duration-700 ${
              isVisible
                ? "opacity-100 translate-y-0"
                : "opacity-0 translate-y-8"
            }`}
          >
            <span className="inline-flex items-center gap-3 text-sm font-mono text-muted-foreground mb-6">
              <span className="w-8 h-px bg-foreground/30" />
              Dành cho nhà phát triển
            </span>
            <h2 className="text-4xl lg:text-6xl font-display tracking-tight mb-8">
              Thiết kế cho
              <br />
              <span className="text-muted-foreground">nhà phát triển.</span>
            </h2>
            <p className="text-xl text-muted-foreground mb-12 leading-relaxed">
              API trực quan và tài liệu chi tiết. Kết nối semantic layer trong
              vài dòng code.
            </p>

            {/* Features */}
            <div className="grid grid-cols-2 gap-6">
              {features.map((feature, index) => (
                <div
                  key={feature.title}
                  className={`transition-all duration-500 ${
                    isVisible
                      ? "opacity-100 translate-y-0"
                      : "opacity-0 translate-y-4"
                  }`}
                  style={{ transitionDelay: `${index * 50 + 200}ms` }}
                >
                  <h3 className="font-medium mb-1">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground">
                    {feature.description}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Code block */}
          <div
            className={`lg:sticky lg:top-32 transition-all duration-700 delay-200 ${
              isVisible
                ? "opacity-100 translate-x-0"
                : "opacity-0 translate-x-8"
            }`}
          >
            <div className="border border-foreground/10">
              {/* Tabs */}
              <div className="flex items-center border-b border-foreground/10">
                {codeExamples.map((example, idx) => (
                  <button
                    key={example.label}
                    type="button"
                    onClick={() => setActiveTab(idx)}
                    className={`px-6 py-4 text-sm font-mono transition-colors relative ${
                      activeTab === idx
                        ? "text-foreground"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {example.label}
                    {activeTab === idx && (
                      <span className="absolute bottom-0 left-0 right-0 h-px bg-foreground" />
                    )}
                  </button>
                ))}
                <div className="flex-1" />
                <button
                  type="button"
                  onClick={handleCopy}
                  className="px-4 py-4 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label="Copy code"
                >
                  {copied ? (
                    <Check className="w-4 h-4 text-green-600" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </button>
              </div>

              {/* Code content */}
              <div className="p-8 font-mono text-sm bg-foreground/[0.01] min-h-[220px]">
                <pre className="text-foreground/80">
                  {codeExamples[activeTab].code
                    .split("\n")
                    .map((line, lineIndex) => (
                      <div
                        key={`${activeTab}-${lineIndex}`}
                        className="leading-loose dev-code-line"
                        style={{ animationDelay: `${lineIndex * 80}ms` }}
                      >
                        <span className="inline-flex">
                          {line.split("").map((char, charIndex) => (
                            <span
                              key={`${activeTab}-${lineIndex}-${charIndex}`}
                              className="dev-code-char"
                              style={{
                                animationDelay: `${lineIndex * 80 + charIndex * 15}ms`,
                              }}
                            >
                              {char === " " ? "\u00A0" : char}
                            </span>
                          ))}
                        </span>
                      </div>
                    ))}
                </pre>
              </div>
            </div>

            {/* Links */}
            <div className="mt-6 flex items-center gap-6 text-sm">
              <span className="text-muted-foreground">
                Tài liệu tham khảo trong project
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
