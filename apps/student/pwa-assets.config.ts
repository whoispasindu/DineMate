import { defineConfig, minimal2023Preset } from "@vite-pwa/assets-generator/config";

const brand = { background: "#1F7A45" };

export default defineConfig({
  preset: {
    ...minimal2023Preset,
    maskable: { ...minimal2023Preset.maskable, padding: 0.1, resizeOptions: brand },
    apple: { ...minimal2023Preset.apple, padding: 0.1, resizeOptions: brand },
  },
  images: ["public/logo.svg"],
});
