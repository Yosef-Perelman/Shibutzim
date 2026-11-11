import { describe, expect, it } from 'vitest';

import {
  currentMonthStart,
  currentWeekStart,
  formatDay,
  formatMonth,
  formatTime,
  formatTimeRange,
  formatWeekRange,
  isPastWeek,
  localDate,
  monthRange,
  shiftMonth,
  shiftWeek,
} from './time';

describe('currentWeekStart', () => {
  it('is the Sunday on or before today in Jerusalem', () => {
    // Monday 9 Nov 2026 12:00 UTC
    expect(currentWeekStart(new Date('2026-11-09T12:00:00Z'))).toBe('2026-11-08');
  });

  it('is the same day when today is a Sunday', () => {
    expect(currentWeekStart(new Date('2026-11-08T09:00:00Z'))).toBe('2026-11-08');
  });

  it('uses the Jerusalem date: Saturday 22:30 UTC is already Sunday there', () => {
    expect(currentWeekStart(new Date('2026-11-14T22:30:00Z'))).toBe('2026-11-15');
  });

  it('still belongs to the old week on Saturday evening in Jerusalem', () => {
    expect(currentWeekStart(new Date('2026-11-14T17:30:00Z'))).toBe('2026-11-08');
  });
});

describe('shiftWeek', () => {
  it('moves by whole weeks in both directions', () => {
    expect(shiftWeek('2026-11-08', 1)).toBe('2026-11-15');
    expect(shiftWeek('2026-11-08', -1)).toBe('2026-11-01');
  });

  it('crosses the end of the year', () => {
    expect(shiftWeek('2026-12-27', 1)).toBe('2027-01-03');
  });

  it('is not confused by the clock change at the end of October', () => {
    expect(shiftWeek('2026-10-25', 1)).toBe('2026-11-01');
  });
});

describe('isPastWeek', () => {
  const now = new Date('2026-11-09T12:00:00Z');
  it('is true only for weeks that started before this week', () => {
    expect(isPastWeek('2026-11-01', now)).toBe(true);
    expect(isPastWeek('2026-11-08', now)).toBe(false);
    expect(isPastWeek('2026-11-15', now)).toBe(false);
  });
});

describe('Jerusalem time formatting', () => {
  it('shows winter time as UTC+2', () => {
    expect(formatTime('2026-11-15T05:00:00Z')).toBe('07:00');
  });

  it('shows summer time as UTC+3', () => {
    expect(formatTime('2026-07-15T04:00:00Z')).toBe('07:00');
  });

  it('formats a range, including one that ends after midnight', () => {
    expect(formatTimeRange('2026-11-15T05:00:00Z', '2026-11-15T13:00:00Z')).toBe('07:00–15:00');
    expect(formatTimeRange('2026-11-15T20:00:00Z', '2026-11-16T04:00:00Z')).toBe('22:00–06:00');
  });

  it('gives the local calendar date of an instant', () => {
    expect(localDate('2026-11-15T23:00:00Z')).toBe('2026-11-16');
  });

  it('formats a plain date as weekday, day and month', () => {
    expect(formatDay('2026-11-15')).toBe('Sun 15 Nov');
  });

  it('formats a week range inside one month and across two', () => {
    expect(formatWeekRange('2026-11-08')).toBe('8–14 Nov');
    expect(formatWeekRange('2026-11-29')).toBe('29 Nov – 5 Dec');
  });
});

describe('months', () => {
  it('finds the first day of this month by the Jerusalem date', () => {
    expect(currentMonthStart(new Date('2026-11-09T12:00:00Z'))).toBe('2026-11-01');
    // 22:30 UTC on 31 Oct is already 1 Nov in Jerusalem (UTC+2).
    expect(currentMonthStart(new Date('2026-10-31T22:30:00Z'))).toBe('2026-11-01');
  });

  it('gives the first and last day of a month, leap years included', () => {
    expect(monthRange('2026-11-01')).toEqual({ from: '2026-11-01', to: '2026-11-30' });
    expect(monthRange('2028-02-01')).toEqual({ from: '2028-02-01', to: '2028-02-29' });
    expect(monthRange('2027-02-01')).toEqual({ from: '2027-02-01', to: '2027-02-28' });
  });

  it('moves by whole months across the end of the year', () => {
    expect(shiftMonth('2026-12-01', 1)).toBe('2027-01-01');
    expect(shiftMonth('2026-01-01', -1)).toBe('2025-12-01');
  });

  it('names a month with its year', () => {
    expect(formatMonth('2026-11-01')).toBe('November 2026');
  });
});
