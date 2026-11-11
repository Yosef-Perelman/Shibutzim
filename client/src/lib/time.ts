// Week and clock helpers. Weeks run Sunday to Saturday and are identified by their Sunday; times are
// shown in Asia/Jerusalem (product-definition §6.3). The server stores UTC, the client only displays.
import dayjs from 'dayjs';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';

dayjs.extend(utc);
dayjs.extend(timezone);

export const TIMEZONE = 'Asia/Jerusalem';
const DATE_FORMAT = 'YYYY-MM-DD';

/** The Sunday that starts the week containing `now`, by the calendar date in Jerusalem. */
export function currentWeekStart(now: Date = new Date()): string {
  const today = dayjs.utc(localDate(now.toISOString()));
  return today.subtract(today.day(), 'day').format(DATE_FORMAT);
}

/** Calendar arithmetic on plain dates, so a clock change never moves a week. */
export function shiftWeek(weekStart: string, weeks: number): string {
  return dayjs
    .utc(weekStart)
    .add(weeks * 7, 'day')
    .format(DATE_FORMAT);
}

/** A week is past once its Sunday is before this week's Sunday (same rule as the server). */
export function isPastWeek(weekStart: string, now: Date = new Date()): boolean {
  return weekStart < currentWeekStart(now);
}

/** `07:00`, 24-hour, Jerusalem. */
export function formatTime(instant: string): string {
  return dayjs(instant).tz(TIMEZONE).format('HH:mm');
}

export function formatTimeRange(startsAt: string, endsAt: string): string {
  return `${formatTime(startsAt)}–${formatTime(endsAt)}`;
}

/** The calendar date (`YYYY-MM-DD`) of an instant in Jerusalem. */
export function localDate(instant: string): string {
  return dayjs(instant).tz(TIMEZONE).format(DATE_FORMAT);
}

/** `Sun 15 Nov` from a plain date. */
export function formatDay(date: string): string {
  return dayjs.utc(date).format('ddd D MMM');
}

/** `8–14 Nov`, or `29 Nov – 5 Dec` when the week spans two months. */
export function formatWeekRange(weekStart: string): string {
  const start = dayjs.utc(weekStart);
  const end = start.add(6, 'day');
  if (start.month() === end.month()) return `${start.format('D')}–${end.format('D MMM')}`;
  return `${start.format('D MMM')} – ${end.format('D MMM')}`;
}

/** The first day (`YYYY-MM-01`) of the month containing `now`, by the Jerusalem date. */
export function currentMonthStart(now: Date = new Date()): string {
  return `${localDate(now.toISOString()).slice(0, 7)}-01`;
}

/** First and last day of a month, both inclusive: the work-day range of a pay period. */
export function monthRange(monthStart: string): { from: string; to: string } {
  const start = dayjs.utc(monthStart);
  return { from: start.format(DATE_FORMAT), to: start.endOf('month').format(DATE_FORMAT) };
}

export function shiftMonth(monthStart: string, months: number): string {
  return dayjs.utc(monthStart).add(months, 'month').format('YYYY-MM-01');
}

/** `November 2026`. */
export function formatMonth(monthStart: string): string {
  return dayjs.utc(monthStart).format('MMMM YYYY');
}
