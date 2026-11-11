import { Alert, Card, Group, Stack, Text, Title } from '@mantine/core';
import { IconAlertTriangle } from '@tabler/icons-react';

import type { Pay } from '../../api/types/pay';
import { formatHours, formatMoney, formatTierBand } from '../../lib/format';
import { formatDay } from '../../lib/time';

export interface PayBreakdownProps {
  pay: Pay;
}

/** Totals, then each work day with its overtime lines. Every number is the server's. */
export function PayBreakdown({ pay }: PayBreakdownProps) {
  return (
    <Stack gap="lg">
      <Card>
        <Stack gap={4}>
          <Text c="ink.6" size="sm">
            Total for the month
          </Text>
          <Text fw={500} fz={32} lh="40px" className="tabular">
            {formatMoney(pay.amount)}
          </Text>
          <Text c="ink.6" className="tabular">
            {formatHours(pay.hours)}
          </Text>
        </Stack>
      </Card>

      {pay.open_entries > 0 ? (
        <Alert color="warning" icon={<IconAlertTriangle size={18} />} title="Open time entries">
          {pay.open_entries === 1
            ? '1 time entry has no clock-out yet and is not included.'
            : `${pay.open_entries} time entries have no clock-out yet and are not included.`}{' '}
          It counts once it is closed.
        </Alert>
      ) : null}

      {pay.days.map((day) => (
        <Card
          key={day.work_day}
          padding="md"
          component="section"
          aria-label={formatDay(day.work_day)}
        >
          <Stack gap="sm">
            <Group justify="space-between" wrap="nowrap">
              <Title order={3}>{formatDay(day.work_day)}</Title>
              <Text fw={500} className="tabular">
                {formatMoney(day.amount)}
              </Text>
            </Group>
            <Text size="sm" c="ink.6" className="tabular">
              {formatHours(day.hours)}
            </Text>
            <Stack gap={4}>
              {day.lines
                .filter((line) => line.seconds > 0)
                .map((line) => (
                  <Group key={line.from_hour} justify="space-between" wrap="nowrap" gap="md">
                    <Text size="sm" className="tabular">
                      {formatTierBand(line.from_hour, line.to_hour)} · ×{line.multiplier}
                    </Text>
                    <Text size="sm" className="tabular" ta="right">
                      {formatHours(line.hours)} · {formatMoney(line.amount)}
                    </Text>
                  </Group>
                ))}
            </Stack>
          </Stack>
        </Card>
      ))}
    </Stack>
  );
}
