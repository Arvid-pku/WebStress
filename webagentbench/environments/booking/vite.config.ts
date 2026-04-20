import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendUrl = `http://127.0.0.1:${process.env.VITE_BACKEND_PORT || 8080}`;

export default defineConfig({
  plugins: [react()],
  base: "/env/booking/",
  optimizeDeps: {
    exclude: ["@webagentbench/shared", "@webagentbench/booking"],
  },
  build: {
    outDir: "../../static/envs/booking",
    emptyOutDir: true,
  },
  server: {
    port: Number(process.env.VITE_SERVER_PORT) || 8084,
    host: "127.0.0.1",
    proxy: {
      "/api": backendUrl,
      "/manifest": backendUrl,
      "/static": backendUrl,
      "/launch": backendUrl,
      "/control": backendUrl,
    },
  },
});
