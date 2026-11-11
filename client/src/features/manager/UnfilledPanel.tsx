import { Alert, Card, Group, List, Stack, Text, Title } from '@mantine/core';
import { IconAlertTriangle, IconCircleCheck } from '@tabler/icons-react';

import type { ScheduleGenerateOut } from '../../api/types/schedule';

export interface UnfilledPanelProps {
  run: ScheduleGenerateOut;
}

/** What the solver reported: the shifts it could not fill, in its own words, and its score. */
export function UnfilledPanel({ run }: UnfilledPanelProps) {
  const { unfilled, score, complete } = run;
  return (
    <Card component="section" aria-label="Last generate">
      <Stack gap="sm">
        <Group justify="space-between" align="baseline">
          <Title order={3}>Last generate</Title>
          <Text size="sm" c="ink.6" className="tabular">
            {score.filled} positions filled · {score.preferred} preferred honored
          </Text>
        </Group>

        {unfilled.length === 0 ? (
          <Group gap="xs" wrap="nowrap">
            <IconCircleCheck size={20} color="var(--mantine-color-success-6)" aria-hidden />
            <Text c="success.6" fw={500}>
              Every shift is fully staffed.
            </Text>
          </Group>
        ) : (
          <Stack gap="xs">
            <Group gap="xs" wrap="nowrap">
              <IconAlertTriangle size={20} color="var(--mantine-color-warning-6)" aria-hidden />
              <Text c="warning.6" fw={500}>
                {unfilled.length === 1 ? '1 shift' : `${unfilled.length} shifts`} could not be fully
                staffed
              </Text>
            </Group>
            <List spacing={4} size="sm" aria-label="Unfilled shifts">
              {unfilled.map((slot) => (
                <List.Item key={slot.shift_id}>{slot.sentence}</List.Item>
              ))}
            </List>
          </Stack>
        )}

        {complete ? null : (
          <Alert color="warning" title="The search did not finish">
            The solver stopped at its step budget, so a better schedule may exist.
          </Alert>
        )}
      </Stack>
    </Card>
  );
}
