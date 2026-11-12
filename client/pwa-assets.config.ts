import { defineConfig, minimal2023Preset } from '@vite-pwa/assets-generator/config';

// `npm run icons` turns public/icon.svg into the PNG and ICO files the manifest and the
// iPhone home screen need. The maskable and Apple icons get the ink background of the design
// system, so the icon never has a white corner.
const INK = '#1f1c42';

export default defineConfig({
  headLinkOptions: { preset: '2023' },
  preset: {
    ...minimal2023Preset,
    maskable: { ...minimal2023Preset.maskable, resizeOptions: { background: INK } },
    apple: { ...minimal2023Preset.apple, resizeOptions: { background: INK } },
  },
  images: ['public/icon.svg'],
});
