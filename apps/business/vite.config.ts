import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  server: { port: 5177 },
  preview: { port: 4177 },
  plugins: [react(), tailwindcss()],
});
