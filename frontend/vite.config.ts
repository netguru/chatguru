import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    globals: true,
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      // Proxy WebSocket to the backend. Target is overridable via WS_PROXY_TARGET
      // so that `docker compose up frontend` can point to chatguru-agent:8000
      // while local dev defaults to localhost:8000.
      "/ws": {
        target: process.env.WS_PROXY_TARGET ?? "http://localhost:8000",
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
