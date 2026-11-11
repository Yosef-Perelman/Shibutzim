import { Alert, Button, Card, Group, Skeleton, Stack, Text } from '@mantine/core';
import { IconAlertCircle, IconClock } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useEffect } from 'react';

import { IconTile } from '../../components/IconTile';
import { formatDay, formatTime, localDate } from '../../lib/time';
import { useTimeStore } from '../../stores/StoreContext';

/** One card, one button: clock in, or clock out with the time you started (product-definition §5.3). */
export const ClockCard = observer(function ClockCard() {
  const store = useTimeStore();

  useEffect(() => {
    void store.load();
  }, [store]);

  if (store.status === 'idle' || store.status === 'loading') {
    return <Skeleton height={96} radius="lg" aria-label="Loading time clock" />;
  }

  if (store.status === 'error') {
    return (
      <Alert color="danger" icon={<IconAlertCircle size={18} />} role="alert" title="Time clock">
        <Stack gap="sm" align="flex-start">
          <Text>{store.error}</Text>
          <Button variant="outline" color="danger" onClick={() => void store.load()}>
            Retry
          </Button>
        </Stack>
      </Alert>
    );
  }

  const entry = store.openEntry;
  return (
    <Card>
      <Stack gap="md">
        <Group wrap="nowrap" gap="md">
          <IconTile icon={IconClock} />
          <Stack gap={0}>
            <Text fw={500}>{entry ? 'You are clocked in' : 'You are not clocked in'}</Text>
            {entry ? (
              <Text size="sm" c="ink.6" className="tabular">
                Since {formatTime(entry.clock_in)} · {formatDay(localDate(entry.clock_in))}
              </Text>
            ) : (
              <Text size="sm" c="ink.6">
                Clock in when your shift starts.
              </Text>
            )}
          </Stack>
        </Group>
        {store.actionError ? (
          <Alert color="danger" icon={<IconAlertCircle size={18} />} role="alert">
            {store.actionError}
          </Alert>
        ) : null}
        <Button
          fullWidth
          loading={store.isBusy}
          onClick={() => void (entry ? store.clockOut() : store.clockIn())}
        >
          {entry ? 'Clock out' : 'Clock in'}
        </Button>
      </Stack>
    </Card>
  );
});
