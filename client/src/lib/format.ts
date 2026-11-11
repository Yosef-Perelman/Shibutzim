// Display formatting for values the server already computed. Money and hours arrive as decimal strings;
// they are only formatted here, never converted to numbers, rounded or summed (ui-rules).

const CURRENCY_SYMBOL = '₪';
const THOUSANDS = /\B(?=(\d{3})+(?!\d))/g;

/** `₪1,213.50`: shekel sign, thousands separators, at least two decimals, nothing rounded. */
export function formatMoney(amount: string): string {
  const negative = amount.startsWith('-');
  const unsigned = negative ? amount.slice(1) : amount;
  const [whole = '0', fraction = ''] = unsigned.split('.');
  return `${negative ? '-' : ''}${CURRENCY_SYMBOL}${whole.replace(THOUSANDS, ',')}.${fraction.padEnd(2, '0')}`;
}

/** The server's display hours with the unit: `9.00 h`. */
export function formatHours(hours: string): string {
  return `${hours} h`;
}

function trimZeros(value: string): string {
  return value.includes('.') ? value.replace(/0+$/, '').replace(/\.$/, '') : value;
}

/** An overtime band of daily hours: `0–8 h`, or `10+ h` for the open-ended one. */
export function formatTierBand(fromHour: string, toHour: string | null): string {
  if (toHour === null) return `${trimZeros(fromHour)}+ h`;
  return `${trimZeros(fromHour)}–${trimZeros(toHour)} h`;
}
