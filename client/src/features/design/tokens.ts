// The tokens of docs/design-system.md as data, so the style preview shows what the document says.

export interface Swatch {
  name: string;
  hex: string;
  use: string;
  /** Contrast note, e.g. "15.5:1 on page". */
  contrast?: string;
}

export const neutralSwatches: Swatch[] = [
  { name: 'page', hex: '#fbfaf9', use: 'page background' },
  { name: 'surface', hex: '#ffffff', use: 'header, dialogs, inputs' },
  { name: 'card', hex: '#f2eeea', use: 'cards and panels, no border' },
  { name: 'card-strong', hex: '#ebe7e2', use: 'card hover, table header' },
  { name: 'line', hex: '#e3ded8', use: 'dividers, input border' },
  { name: 'ink', hex: '#1f1c42', use: 'text, icon tiles', contrast: '15.5:1 on page' },
  { name: 'ink-muted', hex: '#6b677a', use: 'secondary text', contrast: '5.2:1 on page' },
  { name: 'ink-disabled', hex: '#a3a1af', use: 'disabled only', contrast: '2.4:1 (exempt)' },
];

export const brandSwatches: Swatch[] = [
  { name: 'primary', hex: '#2f6fe0', use: 'buttons, links', contrast: '4.7:1 with white' },
  { name: 'primary-hover', hex: '#2b62c9', use: 'hover, pressed', contrast: '5.7:1 with white' },
  { name: 'primary-text', hex: '#245bc4', use: 'link text on tints', contrast: '6.2:1 on white' },
  { name: 'primary-tint', hex: '#e4eefd', use: 'selected row, hover' },
  { name: 'sky', hex: '#4d96f8', use: 'icons, focus ring, decoration only' },
];

export interface TypeStyle {
  role: string;
  size: number;
  lineHeight: number;
  weight: number;
  sample: string;
}

export const typeScale: TypeStyle[] = [
  { role: 'display', size: 40, lineHeight: 48, weight: 400, sample: 'Weekly schedule' },
  { role: 'h1', size: 28, lineHeight: 36, weight: 500, sample: 'My shifts' },
  { role: 'h2', size: 22, lineHeight: 30, weight: 500, sample: 'Sunday 15 Nov' },
  { role: 'h3', size: 18, lineHeight: 26, weight: 500, sample: 'Morning shift' },
  { role: 'body', size: 16, lineHeight: 24, weight: 400, sample: 'Dana is working 07:00–15:00.' },
  { role: 'body-sm', size: 14, lineHeight: 20, weight: 400, sample: 'Needs 3, has 2.' },
  { role: 'caption', size: 12, lineHeight: 16, weight: 500, sample: 'UPDATED 2 MIN AGO' },
];

export const spacingScale = [
  { name: 'xs', px: 4 },
  { name: 'sm', px: 8 },
  { name: 'md', px: 16 },
  { name: 'lg', px: 24 },
  { name: 'xl', px: 32 },
  { name: '2xl', px: 48 },
  { name: '3xl', px: 64 },
];

export const radiusScale = [
  { name: 'radius-sm', px: 8, use: 'inputs' },
  { name: 'radius-md', px: 12, use: 'icon tiles, menus' },
  { name: 'radius-lg', px: 24, use: 'cards, dialogs' },
  { name: 'radius-pill', px: 999, use: 'buttons, badges, pills' },
];
