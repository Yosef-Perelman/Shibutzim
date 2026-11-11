import { SegmentedControl } from '@mantine/core';
import { IconCheck, IconStar, IconX, type Icon } from '@tabler/icons-react';

import type { AvailabilityStatus } from '../api/types/enums';

export interface AvailabilityControlProps {
  value: AvailabilityStatus;
  onChange: (status: AvailabilityStatus) => void;
  /** Read-only weeks: the three pills stay visible but cannot change. */
  disabled?: boolean;
  /** Names the control for screen readers, e.g. "Availability for Sun 07:00". */
  label: string;
}

const OPTIONS: { value: AvailabilityStatus; label: string; icon: Icon; color: string }[] = [
  { value: 'available', label: 'Available', icon: IconCheck, color: 'success' },
  { value: 'preferred', label: 'Preferred', icon: IconStar, color: 'purple' },
  { value: 'unavailable', label: 'Unavailable', icon: IconX, color: 'ink' },
];

/** Three equal tiles, icon above word; the selected one is filled with its status color (design-system §6.2). */
export function AvailabilityControl({
  value,
  onChange,
  disabled,
  label,
}: AvailabilityControlProps) {
  const selected = OPTIONS.find((option) => option.value === value) ?? OPTIONS[2];
  return (
    <SegmentedControl
      fullWidth
      radius="lg"
      size="md"
      aria-label={label}
      disabled={disabled}
      value={value}
      color={selected?.color}
      onChange={(next) => onChange(next as AvailabilityStatus)}
      data={OPTIONS.map(({ value: optionValue, label: text, icon: IconComponent }) => ({
        value: optionValue,
        label: (
          <span
            style={{
              display: 'inline-flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 2,
              fontSize: 14,
            }}
          >
            <IconComponent size={18} aria-hidden />
            {text}
          </span>
        ),
      }))}
    />
  );
}
