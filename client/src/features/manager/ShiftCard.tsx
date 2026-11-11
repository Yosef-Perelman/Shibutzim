import { ActionIcon, Button, Card, Group, Menu, Stack, Text } from '@mantine/core';
import { IconDots, IconPlus } from '@tabler/icons-react';

import type { Assignment } from '../../api/types/schedule';
import { CoverageBadge } from '../../components/StatusBadge';
import { formatDay, formatTimeRange, localDate } from '../../lib/time';
import type { ShiftEntry } from '../../stores/ScheduleStore';

export interface ShiftCardProps {
  entry: ShiftEntry;
  /** Disables every action while another request runs. */
  busy?: boolean;
  onAdd: (entry: ShiftEntry) => void;
  onReplace: (entry: ShiftEntry, assignment: Assignment) => void;
  onRemove: (entry: ShiftEntry, assignment: Assignment) => void;
}

/** One shift of the board: name, time, coverage and the people on it, each with replace / remove. */
export function ShiftCard({ entry, busy, onAdd, onReplace, onRemove }: ShiftCardProps) {
  const { shift, people } = entry;
  const day = formatDay(localDate(shift.starts_at));
  return (
    <Card padding="sm" component="article" aria-label={`${shift.name} ${day}`}>
      <Stack gap="xs">
        <Stack gap={2} align="flex-start">
          <Text fw={500}>{shift.name}</Text>
          <Text size="sm" c="ink.6" className="tabular" style={{ whiteSpace: 'nowrap' }}>
            {formatTimeRange(shift.starts_at, shift.ends_at)}
          </Text>
          <CoverageBadge assigned={shift.assigned_count} required={shift.required_staff} />
        </Stack>

        {people.length === 0 ? (
          <Text size="sm" c="ink.6">
            Nobody assigned
          </Text>
        ) : (
          <Stack gap={0} component="ul" p={0} m={0}>
            {people.map((person) => (
              <Group
                key={person.id}
                component="li"
                justify="space-between"
                wrap="nowrap"
                gap="xs"
                style={{ listStyle: 'none' }}
              >
                <Text size="sm">{person.user_name}</Text>
                <Menu position="bottom-end" withinPortal>
                  <Menu.Target>
                    <ActionIcon
                      variant="subtle"
                      size={36}
                      radius="xl"
                      disabled={busy}
                      aria-label={`Actions for ${person.user_name}`}
                    >
                      <IconDots size={18} />
                    </ActionIcon>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Item onClick={() => onReplace(entry, person)}>Replace…</Menu.Item>
                    <Menu.Item color="danger" onClick={() => onRemove(entry, person)}>
                      Remove
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              </Group>
            ))}
          </Stack>
        )}

        <Button
          variant="light"
          leftSection={<IconPlus size={16} />}
          styles={{ root: { height: 36 } }}
          disabled={busy}
          aria-label={`Add someone to ${shift.name} on ${day}`}
          onClick={() => onAdd(entry)}
        >
          Add
        </Button>
      </Stack>
    </Card>
  );
}
