import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento, /api é encaminhado ao motor local (sem CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.QA_ENGINE_URL ?? "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
