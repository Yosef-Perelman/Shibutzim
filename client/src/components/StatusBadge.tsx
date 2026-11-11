import { Badge } from '@mantine/core';
import {
  IconAlertCircle,
  IconCalendarOff,
  IconCheck,
  IconCircleCheck,
  IconPencil,
  IconStar,
  IconX,
  type Icon,
} from '@tabler/icons-react';

import type { AvailabilityStatus, ScheduleStatus } from '../api/types/enums';
import { toneColors, type Tone } from '../theme';

export interface ToneBadgeProps {
  tone: Tone;
  label: string;
  icon?: Icon;
}

/** Pill with the status colors, an icon and a word: color is never the only signal. */
export function ToneBadge({ tone, label, icon: IconComponent }: ToneBadgeProps) {
  const { text, fill } = toneColors[tone];
  return (
    <Badge
      radius="xl"
      size="lg"
      tt="none"
      fw={500}
      styles={{ root: { backgroundColor: fill, color: text } }}
      leftSection={IconComponent ? <IconComponent size={14} aria-hidden /> : undefined}
    >
      {label}
    </Badge>
  );
}

const AVAILABILITY: Record<AvailabilityStatus, { tone: Tone; label: string; icon: Icon }> = {
  available: { tone: 'success', label: 'Available', icon: IconCheck },
  preferred: { tone: 'purple', label: 'Preferred', icon: IconStar },
  unavailable: { tone: 'neutral', label: 'Unavailable', icon: IconX },
};

export interface AvailabilityBadgeProps {
  status: AvailabilityStatus;
}

export function AvailabilityBadge({ status }: AvailabilityBadgeProps) {
  return <ToneBadge {...AVAILABILITY[status]} />;
}

export interface ScheduleStatusBadgeProps {
  /** `null` means the week has no schedule yet. */
  status: ScheduleStatus | null;
}

export function ScheduleStatusBadge({ status }: ScheduleStatusBadgeProps) {
  if (status === 'draft') return <ToneBadge tone="warning" label="Draft" icon={IconPencil} />;
  if (status === 'published') {
    return <ToneBadge tone="success" label="Published" icon={IconCircleCheck} />;
  }
  return <ToneBadge tone="neutral" label="No schedule" icon={IconCalendarOff} />;
}

export interface CoverageBadgeProps {
  assigned: number;
  required: number;
}

/** "2 / 3": green when the shift is fully staffed, red while it is short. */
export function CoverageBadge({ assigned, required }: CoverageBadgeProps) {
  const isShort = assigned < required;
  return (
    <ToneBadge
      tone={isShort ? 'danger' : 'success'}
      label={`${assigned} / ${required}`}
      icon={isShort ? IconAlertCircle : IconCheck}
    />
  );
}
