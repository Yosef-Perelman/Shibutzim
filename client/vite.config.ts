import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import { defineConfig } from 'vitest/config';

// The dev server proxies /api to the FastAPI server so the browser stays same-origin
// (plan 003, open question 6). VITE_API_URL can still point the client at another host.
//
// The app installs on a phone home screen (plan 005). The service worker precaches the app shell
// only: /api is never part of a navigation fallback and has no runtime cache, so no signed-in
// data is ever served from a cache. Tests leave the plugin out.
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    ...(mode === 'test'
      ? []
      : [
          VitePWA({
            registerType: 'autoUpdate',
            includeAssets: ['icon.svg', 'favicon.ico', 'apple-touch-icon-180x180.png'],
            manifest: {
              name: 'Shibutzim',
              short_name: 'Shibutzim',
              description: 'Shift scheduling and pay for small teams of hourly workers',
              lang: 'en',
              start_url: '/',
              scope: '/',
              display: 'standalone',
              background_color: '#fbfaf9',
              theme_color: '#ffffff',
              icons: [
                { src: 'pwa-64x64.png', sizes: '64x64', type: 'image/png' },
                { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
                { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
                {
                  src: 'maskable-icon-512x512.png',
                  sizes: '512x512',
                  type: 'image/png',
                  purpose: 'maskable',
                },
              ],
            },
            workbox: {
              globPatterns: ['**/*.{js,css,html,ico,png,svg,webmanifest}'],
              navigateFallback: '/index.html',
              navigateFallbackDenylist: [/^\/api\//],
              cleanupOutdatedCaches: true,
            },
          }),
        ]),
  ],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
}));
