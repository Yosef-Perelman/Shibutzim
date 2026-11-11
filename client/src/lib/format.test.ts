import { describe, expect, it } from 'vitest';

import { formatHours, formatMoney, formatTierBand } from './format';

describe('formatMoney', () => {
  it('shows the shekel sign and two decimals', () => {
    expect(formatMoney('412.50')).toBe('₪412.50');
  });

  it('pads a short fraction and groups thousands', () => {
    expect(formatMoney('1213.5')).toBe('₪1,213.50');
    expect(formatMoney('1234567.00')).toBe('₪1,234,567.00');
  });

  it('shows zero with two decimals', () => {
    expect(formatMoney('0')).toBe('₪0.00');
    expect(formatMoney('0.00')).toBe('₪0.00');
  });

  it('keeps the sign in front of the shekel sign', () => {
    expect(formatMoney('-5.5')).toBe('-₪5.50');
  });

  it('never rounds: extra decimals from the server stay as they are', () => {
    expect(formatMoney('10.125')).toBe('₪10.125');
  });
});

describe('formatHours', () => {
  it("appends the unit to the server's display hours", () => {
    expect(formatHours('9.00')).toBe('9.00 h');
    expect(formatHours('0.50')).toBe('0.50 h');
  });
});

describe('formatTierBand', () => {
  it('writes a closed band as from–to hours without trailing zeros', () => {
    expect(formatTierBand('0', '8')).toBe('0–8 h');
    expect(formatTierBand('8.00', '10.00')).toBe('8–10 h');
    expect(formatTierBand('8.50', '10')).toBe('8.5–10 h');
  });

  it('writes the open-ended band as "from+"', () => {
    expect(formatTierBand('10', null)).toBe('10+ h');
  });
});
