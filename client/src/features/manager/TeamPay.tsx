import {
  Badge,
  Card,
  Drawer,
  Group,
  Stack,
  Table,
  Text,
  Title,
  UnstyledButton,
} from '@mantine/core';
import { IconAlertTriangle, IconUsers } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useEffect, useState } from 'react';

import type { TeamPayRow } from '../../api/types/pay';
import { EmptyState, ErrorState, LoadingState } from '../../components/StateViews';
import { PeriodNavigator } from '../../components/PeriodNavigator';
import { formatHours, formatMoney } from '../../lib/format';
import { currentMonthStart, formatMonth } from '../../lib/time';
import { usePayStore } from '../../stores/StoreContext';
import { PayBreakdown } from '../pay/PayBreakdown';

/** Every user's hours and pay for a month; a row opens that person's breakdown (managers only). */
export const TeamPay = observer(function TeamPay() {
  const store = usePayStore();
  const [selected, setSelected] = useState<TeamPayRow | null>(null);

  useEffect(() => {
    void store.loadTeam();
    return () => store.closePay();
  }, [store]);

  function open(row: TeamPayRow) {
    setSelected(row);
    void store.loadPay(row.user_id);
  }

  function close() {
    setSelected(null);
    store.closePay();
  }

  let body;
  if (store.teamStatus === 'idle' || store.teamStatus === 'loading') {
    body = <LoadingState rows={4} />;
  } else if (store.teamStatus === 'error') {
    body = <ErrorState message={store.teamError ?? ''} onRetry={() => void store.loadTeam()} />;
  } else if (!store.team || store.team.users.length === 0) {
    body = (
      <EmptyState
        icon={IconUsers}
        title="No one to show"
        description={`There are no users with time entries in ${formatMonth(store.monthStart)}.`}
      />
    );
  } else {
    const team = store.team;
    body = (
      <Card padding={0} style={{ overflowX: 'auto' }}>
        <Table highlightOnHover aria-label={`Team pay for ${formatMonth(store.monthStart)}`}>
          <Table.Thead bg="sand.2">
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th ta="right">Rate</Table.Th>
              <Table.Th ta="right">Hours</Table.Th>
              <Table.Th ta="right">Amount</Table.Th>
              <Table.Th>Open entries</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {team.users.map((row) => (
              <Table.Tr key={row.user_id} onClick={() => open(row)} style={{ cursor: 'pointer' }}>
                <Table.Td>
                  <UnstyledButton
                    onClick={(event) => {
                      event.stopPropagation();
                      open(row);
                    }}
                    aria-label={`Show the pay breakdown of ${row.name}`}
                    mih={44}
                  >
                    <Group gap="xs" wrap="nowrap">
                      <Text fw={500}>{row.name}</Text>
                      <Badge color="ink" variant="light" tt="capitalize">
                        {row.role}
                      </Badge>
                    </Group>
                  </UnstyledButton>
                </Table.Td>
                <Table.Td ta="right" className="tabular">
                  {formatMoney(row.hourly_rate)}
                </Table.Td>
                <Table.Td ta="right" className="tabular">
                  {formatHours(row.hours)}
                </Table.Td>
                <Table.Td ta="right" className="tabular">
                  {formatMoney(row.amount)}
                </Table.Td>
                <Table.Td>
                  {row.open_entries > 0 ? (
                    <Group gap={4} wrap="nowrap">
                      <IconAlertTriangle
                        size={16}
                        color="var(--mantine-color-warning-6)"
                        aria-hidden
                      />
                      <Text size="sm" c="warning.6">
                        {row.open_entries} open
                      </Text>
                    </Group>
                  ) : (
                    <Text size="sm" c="ink.6">
                      None
                    </Text>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
          <Table.Tfoot>
            <Table.Tr fw={500}>
              <Table.Td>Total</Table.Td>
              <Table.Td />
              <Table.Td ta="right" className="tabular">
                {formatHours(team.hours)}
              </Table.Td>
              <Table.Td ta="right" className="tabular">
                {formatMoney(team.amount)}
              </Table.Td>
              <Table.Td />
            </Table.Tr>
          </Table.Tfoot>
        </Table>
      </Card>
    );
  }

  let drawerBody;
  if (store.payStatus === 'error') {
    drawerBody = (
      <ErrorState message={store.payError ?? ''} onRetry={() => void store.reloadPay()} />
    );
  } else if (store.pay && store.payStatus === 'loaded') {
    drawerBody =
      store.hasDays || store.pay.open_entries > 0 ? (
        <PayBreakdown pay={store.pay} />
      ) : (
        <Text c="ink.6">There are no time entries in {formatMonth(store.monthStart)}.</Text>
      );
  } else {
    drawerBody = <LoadingState rows={2} />;
  }

  return (
    <Stack gap="lg">
      <Title order={1}>Team pay</Title>
      <PeriodNavigator
        label={formatMonth(store.monthStart)}
        previousLabel="Previous month"
        nextLabel="Next month"
        onPrevious={() => void store.goToMonth(-1)}
        onNext={() => void store.goToMonth(1)}
        resetLabel={store.monthStart === currentMonthStart() ? undefined : 'This month'}
        onReset={() => void store.goToCurrentMonth()}
      />
      {body}
      <Drawer
        opened={selected !== null}
        onClose={close}
        position="right"
        size="md"
        title={selected ? `${selected.name} · ${formatMonth(store.monthStart)}` : ''}
      >
        {drawerBody}
      </Drawer>
    </Stack>
  );
});
