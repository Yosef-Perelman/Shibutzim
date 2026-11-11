import { Alert, Badge, Button, Card, Group, List, Stack, Text, Title } from '@mantine/core';
import { IconAlertCircle, IconCalendarEvent, IconCheck, IconX } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useState } from 'react';
import { Link } from 'react-router';

import { IconTile } from '../../components/IconTile';
import { formatDay, formatWeekRange } from '../../lib/time';
import type { ChatEntry } from '../../stores/AssistantStore';
import { useAssistantStore } from '../../stores/StoreContext';

export interface ProposalCardProps {
  entry: ChatEntry;
}

/**
 * A schedule the assistant prepared. Nothing is saved until Confirm: that calls the normal generate
 * endpoint through the store, so the server's rules (a published week is refused) apply.
 */
export const ProposalCard = observer(function ProposalCard({ entry }: ProposalCardProps) {
  const store = useAssistantStore();
  const [showShifts, setShowShifts] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const proposal = entry.proposal;
  if (!proposal) return null;

  async function confirm() {
    setError(null);
    const result = await store.confirmProposal(entry.id);
    if (!result.ok) setError(result.message);
  }

  return (
    <Card bg="shibutzim.1" padding="md" aria-label="Schedule proposal">
      <Stack gap="sm">
        <Group gap="sm" wrap="nowrap" align="center">
          <IconTile icon={IconCalendarEvent} size={32} />
          <Title order={3}>Proposed schedule for {formatWeekRange(proposal.week_start)}</Title>
        </Group>
        <Text>{proposal.summary}</Text>
        {proposal.unavailable.length > 0 ? (
          <List size="sm" spacing={2} aria-label="Days off">
            {proposal.unavailable.map((off) => (
              <List.Item key={`${off.user_id}-${off.day}`}>
                {off.name} is off {formatDay(off.day)}
              </List.Item>
            ))}
          </List>
        ) : null}
        {proposal.unfilled.length > 0 ? (
          <List size="sm" spacing={2} aria-label="Shifts short of staff">
            {proposal.unfilled.map((sentence) => (
              <List.Item key={sentence}>{sentence}</List.Item>
            ))}
          </List>
        ) : null}
        <Button
          variant="subtle"
          size="compact-md"
          style={{ alignSelf: 'flex-start' }}
          onClick={() => setShowShifts((shown) => !shown)}
        >
          {showShifts ? 'Hide shifts' : 'Show shifts'}
        </Button>
        {showShifts ? (
          <Stack gap={4}>
            {proposal.assignments.map((shift) => (
              <div key={shift.shift_id}>
                <Text size="sm" fw={500}>
                  {formatDay(shift.date)} · {shift.name} {shift.start}–{shift.end}
                </Text>
                <Text size="sm" c="ink.6">
                  {shift.people.length > 0 ? shift.people.join(', ') : 'Nobody'}
                </Text>
              </div>
            ))}
          </Stack>
        ) : null}
        {entry.proposalState === 'pending' ? (
          <>
            {proposal.replaces_draft ? (
              <Text size="sm" c="warning.6">
                Confirming replaces the current draft of that week.
              </Text>
            ) : null}
            {error ? (
              <Alert color="danger" icon={<IconAlertCircle size={18} />}>
                {error}
              </Alert>
            ) : null}
            <Group gap="sm">
              <Button loading={store.isConfirming} onClick={() => void confirm()}>
                Confirm
              </Button>
              <Button
                variant="subtle"
                disabled={store.isConfirming}
                onClick={() => store.dismissProposal(entry.id)}
              >
                Cancel
              </Button>
            </Group>
          </>
        ) : null}
        {entry.proposalState === 'confirmed' ? (
          <Group gap="sm">
            <Badge color="success" variant="light" size="lg" leftSection={<IconCheck size={14} />}>
              Draft created
            </Badge>
            <Button component={Link} to="/manager/schedule" variant="outline">
              Open schedule
            </Button>
          </Group>
        ) : null}
        {entry.proposalState === 'cancelled' ? (
          <Badge color="ink" variant="light" size="lg" leftSection={<IconX size={14} />}>
            Proposal cancelled
          </Badge>
        ) : null}
      </Stack>
    </Card>
  );
});
