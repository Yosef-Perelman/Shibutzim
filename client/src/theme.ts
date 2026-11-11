// The Mantine theme. It implements docs/design-system.md; change that document first.
import {
  Button,
  Card,
  createTheme,
  Input,
  type MantineColorsTuple,
  Paper,
  Tabs,
  Table,
} from '@mantine/core';

const FONT_STACK =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

// Each scale has ten shades; shade 6 is the color the design system names (text or fill).
const shibutzim: MantineColorsTuple = [
  '#f1f6fe',
  '#e4eefd', // primary-tint
  '#aecdfc',
  '#7fb0fa',
  '#4d96f8', // sky: icons, focus ring, decoration, never behind small text
  '#3c82ee',
  '#2f6fe0', // primary
  '#2b62c9', // primary-hover
  '#2455ad',
  '#1d4590',
];

const ink: MantineColorsTuple = [
  '#f5f4f7',
  '#e8e6ee',
  '#d3d0dd',
  '#b8b5c5',
  '#a3a1af', // ink-disabled
  '#85829a',
  '#6b677a', // ink-muted
  '#4a4660',
  '#2f2b52',
  '#1f1c42', // ink
];

const sand: MantineColorsTuple = [
  '#fbfaf9', // page
  '#f2eeea', // card
  '#ebe7e2', // card-strong
  '#e3ded8', // line
  '#d3ccc4',
  '#bdb5ab',
  '#9a9188',
  '#6f675f',
  '#4d4740',
  '#2c2824',
];

const success: MantineColorsTuple = [
  '#f1faf4',
  '#e3f4ea',
  '#c4e6d1',
  '#9bd2b2',
  '#6ebb90',
  '#3f9f6c',
  '#166c3b',
  '#125a32',
  '#0e4727',
  '#0a341c',
];

const warning: MantineColorsTuple = [
  '#fffaf0',
  '#fdf0d5',
  '#fbe0a8',
  '#f6cc78',
  '#efb64a',
  '#c98a14',
  '#8a5a00',
  '#724a00',
  '#5b3b00',
  '#442c00',
];

const danger: MantineColorsTuple = [
  '#fef5f4',
  '#fde8e6',
  '#fbcfca',
  '#f6aea6',
  '#ee857a',
  '#d9564a',
  '#b42318',
  '#991d14',
  '#7f1810',
  '#65120c',
];

const purple: MantineColorsTuple = [
  '#f6f4fd',
  '#ece8fb',
  '#d8d0f6',
  '#bfb2ef',
  '#a28fe5',
  '#7e66d6',
  '#5b3fc4',
  '#4d34a8',
  '#3f2a8c',
  '#312070',
];

export type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'purple';

// Text on fill pairs of design-system §2.3, used where Mantine's own variants are not exact.
export const toneColors: Record<Tone, { text: string; fill: string }> = {
  success: { text: '#166c3b', fill: '#e3f4ea' },
  warning: { text: '#8a5a00', fill: '#fdf0d5' },
  danger: { text: '#b42318', fill: '#fde8e6' },
  info: { text: '#2155b8', fill: '#e4eefd' },
  neutral: { text: '#5f5b70', fill: '#ebe7e2' },
  purple: { text: '#5b3fc4', fill: '#ece8fb' },
};

export const shadows = {
  header: '0 2px 8px rgba(31, 28, 66, 0.08)',
  overlay: '0 12px 32px rgba(31, 28, 66, 0.16)',
};

export const theme = createTheme({
  primaryColor: 'shibutzim',
  primaryShade: 6,
  colors: { shibutzim, ink, sand, success, warning, danger, purple },
  white: '#ffffff',
  black: '#1f1c42',
  autoContrast: true,
  focusRing: 'always',
  fontFamily: FONT_STACK,
  headings: {
    fontFamily: FONT_STACK,
    fontWeight: '500',
    sizes: {
      h1: { fontSize: '28px', lineHeight: '36px' },
      h2: { fontSize: '22px', lineHeight: '30px' },
      h3: { fontSize: '18px', lineHeight: '26px' },
    },
  },
  fontSizes: { xs: '12px', sm: '14px', md: '16px', lg: '18px', xl: '22px' },
  lineHeights: { xs: '16px', sm: '20px', md: '24px', lg: '26px', xl: '30px' },
  spacing: { xs: '4px', sm: '8px', md: '16px', lg: '24px', xl: '32px' },
  radius: { xs: '4px', sm: '8px', md: '12px', lg: '24px', xl: '999px' },
  defaultRadius: 'lg',
  shadows: {
    xs: 'none',
    sm: shadows.header,
    md: shadows.header,
    lg: shadows.overlay,
    xl: shadows.overlay,
  },
  other: { shadows },
  components: {
    Button: Button.extend({
      defaultProps: { radius: 'xl', size: 'md', fw: 500 },
      styles: { root: { height: 44, paddingInline: 24 } },
    }),
    Input: Input.extend({
      defaultProps: { radius: 'sm', size: 'md' },
      styles: { input: { minHeight: 44, borderColor: 'var(--mantine-color-sand-3)' } },
    }),
    Card: Card.extend({
      defaultProps: { radius: 'lg', padding: 'lg', withBorder: false },
      styles: { root: { backgroundColor: 'var(--mantine-color-sand-1)' } },
    }),
    Paper: Paper.extend({ defaultProps: { radius: 'lg' } }),
    Tabs: Tabs.extend({ defaultProps: { color: 'ink' } }),
    Table: Table.extend({ defaultProps: { verticalSpacing: 'sm', horizontalSpacing: 'md' } }),
  },
});
