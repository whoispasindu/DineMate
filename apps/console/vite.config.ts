import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  server: { port: 5174 },
  preview: { port: 4174 },
  plugins: [react(), tailwindcss()],
});
