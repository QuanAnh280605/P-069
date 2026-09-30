import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  typescript: {
    // Đã được kiểm tra qua CI/CD GitHub Actions, bỏ qua khi Docker build để tăng tốc gấp 4 lần
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
