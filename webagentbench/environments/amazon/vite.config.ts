import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendUrl = `http://127.0.0.1:${process.env.VITE_BACKEND_PORT || 8080}`;

export default defineConfig({
  plugins: [react()],
  base: "/env/amazon/",
  optimizeDeps: {
    exclude: ["@webagentbench/shared", "@webagentbench/amazon"],
  },
  build: {
    outDir: "../../static/envs/amazon",
    emptyOutDir: true,
  },
  server: {
    port: Number(process.env.VITE_SERVER_PORT) || 4174,
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
