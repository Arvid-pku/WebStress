import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  base: "/env/robinhood/",
  optimizeDeps: { exclude: ["@webagentbench/shared", "@webagentbench/robinhood"] },
  build: { outDir: "../../static/envs/robinhood", emptyOutDir: true },
  server: {
    port: 4174,
    host: "127.0.0.1",
    proxy: {
      "/api": "http://127.0.0.1:8080",
      "/manifest": "http://127.0.0.1:8080",
      "/static": "http://127.0.0.1:8080",
      "/launch": "http://127.0.0.1:8080",
    },
  },
});
