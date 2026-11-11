import { ActionIcon, Button, Group, Text } from '@mantine/core';
import { IconChevronLeft, IconChevronRight } from '@tabler/icons-react';

export interface PeriodNavigatorProps {
  /** The period shown between the arrows, e.g. "8–14 Nov" or "November 2026". */
  label: string;
  previousLabel: string;
  nextLabel: string;
  onPrevious: () => void;
  onNext: () => void;
  /** Shown as a subtle button next to the label; give `undefined` to hide it. */
  resetLabel?: string;
  onReset?: () => void;
  /** Stops navigation, e.g. while a form has unsaved changes. */
  disabled?: boolean;
}

/** Arrows and a label for moving through weeks or months (design-system §6.4). */
export function PeriodNavigator(props: PeriodNavigatorProps) {
  const { label, previousLabel, nextLabel, onPrevious, onNext, resetLabel, onReset, disabled } =
    props;
  return (
    <Group justify="space-between" wrap="nowrap" gap="xs">
      <ActionIcon
        variant="subtle"
        size={44}
        radius="xl"
        aria-label={previousLabel}
        disabled={disabled}
        onClick={onPrevious}
      >
        <IconChevronLeft size={22} />
      </ActionIcon>
      <Group gap="sm" justify="center" wrap="wrap">
        <Text fw={500} size="lg" className="tabular" aria-live="polite">
          {label}
        </Text>
        {resetLabel && onReset ? (
          <Button
            variant="subtle"
            styles={{ root: { height: 36 } }}
            disabled={disabled}
            onClick={onReset}
          >
            {resetLabel}
          </Button>
        ) : null}
      </Group>
      <ActionIcon
        variant="subtle"
        size={44}
        radius="xl"
        aria-label={nextLabel}
        disabled={disabled}
        onClick={onNext}
      >
        <IconChevronRight size={22} />
      </ActionIcon>
    </Group>
  );
}
