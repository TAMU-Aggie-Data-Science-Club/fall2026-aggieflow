import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } }, // shadcn imports "@/..."
  server: { port: 5173 }, // the API's default ALLOWED_ORIGINS is http://localhost:5173
});
