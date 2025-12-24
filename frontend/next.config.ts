import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  
  reactCompiler: true,

  // cacheComponents requires all dynamic routes to be wrapped in Suspense
  // Disabled for now due to compatibility issues with client-side routing
  // cacheComponents: true,
  
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: process.env.BACKEND_URL
          ? `${process.env.BACKEND_URL}/api/:path*`
          : "http://localhost:8000/api/:path*",
      },
    ];
  },
  
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
