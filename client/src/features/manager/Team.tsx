import { Badge, Button, Card, Group, Stack, Table, Text, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconCheck, IconUserPlus, IconUsers, IconX } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useEffect, useState } from 'react';

import type { User } from '../../api/types/user';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { EmptyState, ErrorState, LoadingState } from '../../components/StateViews';
import { ToneBadge } from '../../components/StatusBadge';
import { formatMoney } from '../../lib/format';
import { OK } from '../../stores/ScheduleStore';
import { useAuthStore, useTeamStore } from '../../stores/StoreContext';
import { AddPersonDialog } from './AddPersonDialog';

/** The people of the team: add someone, or deactivate and reactivate (managers only). */
export const Team = observer(function Team() {
  const store = useTeamStore();
  const currentUserId = useAuthStore().user?.id;
  const [adding, setAdding] = useState(false);
  const [deactivating, setDeactivating] = useState<User | null>(null);

  useEffect(() => {
    void store.load();
  }, [store]);

  async function reactivate(user: User) {
    const result = await store.setActive(user, true);
    if (result.ok) {
      notifications.show({ color: 'success', message: `${user.name} can sign in again.` });
    } else {
      notifications.show({ color: 'danger', title: 'Could not do that', message: result.message });
    }
  }

  const addButton = (
    <Button leftSection={<IconUserPlus size={18} aria-hidden />} onClick={() => setAdding(true)}>
      Add person
    </Button>
  );

  let body;
  if (store.status === 'idle' || store.status === 'loading') {
    body = <LoadingState rows={4} />;
  } else if (store.status === 'error') {
    body = <ErrorState message={store.error ?? ''} onRetry={() => void store.load()} />;
  } else if (store.people.length === 0) {
    body = (
      <EmptyState
        icon={IconUsers}
        title="No one on the team yet"
        description="Add the first person to start scheduling."
        action={addButton}
      />
    );
  } else {
    body = (
      <Card padding={0} style={{ overflowX: 'auto' }}>
        <Table highlightOnHover aria-label="Team members">
          <Table.Thead bg="sand.2">
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Email</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th ta="right">Rate</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th ta="right">Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {store.people.map((person) => (
              <Table.Tr key={person.id}>
                <Table.Td>
                  <Group gap="xs" wrap="nowrap">
                    <Text fw={500}>{person.name}</Text>
                    {person.id === currentUserId ? (
                      <Badge color="ink" variant="outline" tt="none">
                        You
                      </Badge>
                    ) : null}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{person.email}</Text>
                </Table.Td>
                <Table.Td>
                  <Badge color="ink" variant="light" tt="capitalize">
                    {person.role}
                  </Badge>
                </Table.Td>
                <Table.Td ta="right" className="tabular">
                  {formatMoney(person.hourly_rate)}
                </Table.Td>
                <Table.Td>
                  {person.is_active ? (
                    <ToneBadge tone="success" label="Active" icon={IconCheck} />
                  ) : (
                    <ToneBadge tone="neutral" label="Inactive" icon={IconX} />
                  )}
                </Table.Td>
                <Table.Td ta="right">
                  {person.id === currentUserId ? null : person.is_active ? (
                    <Button
                      variant="subtle"
                      color="danger"
                      onClick={() => setDeactivating(person)}
                      aria-label={`Deactivate ${person.name}`}
                    >
                      Deactivate
                    </Button>
                  ) : (
                    <Button
                      variant="subtle"
                      onClick={() => void reactivate(person)}
                      aria-label={`Reactivate ${person.name}`}
                    >
                      Reactivate
                    </Button>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Card>
    );
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="flex-start" wrap="wrap">
        <Title order={1}>Team</Title>
        {store.status === 'loaded' && store.people.length > 0 ? addButton : null}
      </Group>
      {body}
      <AddPersonDialog
        opened={adding}
        onSubmit={(person) => store.addPerson(person)}
        onClose={() => setAdding(false)}
        onSuccess={(name) =>
          notifications.show({ color: 'success', message: `${name} was added to the team.` })
        }
      />
      <ConfirmDialog
        opened={deactivating !== null}
        title={deactivating ? `Deactivate ${deactivating.name}?` : ''}
        message={
          deactivating
            ? `${deactivating.name} will not be able to sign in or be scheduled. Their hours and pay history stay, and you can reactivate them at any time.`
            : ''
        }
        confirmLabel="Deactivate"
        confirmColor="danger"
        onConfirm={() =>
          deactivating ? store.setActive(deactivating, false) : Promise.resolve(OK)
        }
        onClose={() => setDeactivating(null)}
        onSuccess={() =>
          notifications.show({
            color: 'success',
            message: `${deactivating?.name ?? 'The person'} was deactivated.`,
          })
        }
      />
    </Stack>
  );
});
