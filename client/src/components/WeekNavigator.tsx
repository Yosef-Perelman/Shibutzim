import { currentWeekStart, formatWeekRange } from '../lib/time';
import { PeriodNavigator } from './PeriodNavigator';

export interface WeekNavigatorProps {
  weekStart: string;
  onPrevious: () => void;
  onNext: () => void;
  onToday?: () => void;
  disabled?: boolean;
}

/** Previous / next week with the date range between them; "This week" appears when away from it. */
export function WeekNavigator({
  weekStart,
  onPrevious,
  onNext,
  onToday,
  disabled,
}: WeekNavigatorProps) {
  const isThisWeek = weekStart === currentWeekStart();
  return (
    <PeriodNavigator
      label={formatWeekRange(weekStart)}
      previousLabel="Previous week"
      nextLabel="Next week"
      onPrevious={onPrevious}
      onNext={onNext}
      resetLabel={isThisWeek ? undefined : 'This week'}
      onReset={onToday}
      disabled={disabled}
    />
  );
}
