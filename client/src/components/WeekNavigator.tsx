import { ActionIcon, Button, Group, Text } from '@mantine/core';
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react';

import { currentWeekStart, formatWeekRange } from '../lib/time';

export interface WeekNavigatorProps {
  weekStart: string;
  onPrevious: () => void;
  onNext: () => void;
  onToday?: () => void;
}

/** Previous / next week with the date range between them; "This week" appears when away from it. */
export function WeekNavigator({ weekStart, onPrevious, onNext, onToday }: WeekNavigatorProps) {
  const isThisWeek = weekStart === currentWeekStart();
  return (
    <Group justify="space-between" wrap="nowrap" gap="xs">
      <ActionIcon
        variant="subtle"
        size={44}
        radius="xl"
        aria-label="Previous week"
        onClick={onPrevious}
      >
        <IconChevronLeft size={22} />
      </ActionIcon>
      <Group gap="sm" justify="center" wrap="wrap">
        <Text fw={500} size="lg" className="tabular" aria-live="polite">
          {formatWeekRange(weekStart)}
        </Text>
        {!isThisWeek && onToday ? (
          <Button variant="subtle" styles={{ root: { height: 36 } }} onClick={onToday}>
            This week
          </Button>
        ) : null}
      </Group>
      <ActionIcon variant="subtle" size={44} radius="xl" aria-label="Next week" onClick={onNext}>
        <IconChevronRight size={22} />
      </ActionIcon>
    </Group>
  );
}
