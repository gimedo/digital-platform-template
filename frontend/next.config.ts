import type { NextConfig } from "next";

// El navegador siempre habla con el mismo origen (/api/...). Next reenvía al backend FastAPI.
// Así la cookie de sesión es de primera parte y no hace falta configurar CORS.
const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
