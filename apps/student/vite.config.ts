import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

const MENUS_AND_HOURS = /^\/api\/v1\/(canteens\/[^/]+\/shops|shops\/[^/]+\/(menu|hours))/;

export default defineConfig({
  server: { port: 5173 },
  preview: { port: 4173 },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "prompt",
      includeAssets: ["favicon.svg", "favicon.ico", "apple-touch-icon-180x180.png"],
      manifest: {
        name: "DineMate",
        short_name: "DineMate",
        description: "Find a free canteen seat in seconds. Seat counts are estimates.",
        display: "standalone",
        start_url: "/?source=pwa",
        scope: "/",
        theme_color: "#1F7A45",
        background_color: "#F3F7F2",
        icons: [
          { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
          { src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
          { src: "maskable-icon-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
        runtimeCaching: [
          {
            urlPattern: ({ request, sameOrigin }) => sameOrigin && request.destination === "image",
            handler: "CacheFirst",
            options: { cacheName: "sample-art", expiration: { maxEntries: 80 } },
          },
          {
            urlPattern: ({ url }) => MENUS_AND_HOURS.test(url.pathname),
            handler: "StaleWhileRevalidate",
            options: { cacheName: "menus-and-hours" },
          },
          {
            urlPattern: ({ url }) => url.pathname.startsWith("/api/") || url.pathname.startsWith("/ws/"),
            handler: "NetworkOnly",
          },
        ],
      },
    }),
  ],
});
