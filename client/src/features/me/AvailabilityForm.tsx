import { Alert, Button, Card, Stack, Text, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertCircle, IconCalendarOff, IconInfoCircle } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useEffect } from 'react';

import { AvailabilityControl } from '../../components/AvailabilityControl';
import { EmptyState, ErrorState, LoadingState } from '../../components/StateViews';
import { WeekNavigator } from '../../components/WeekNavigator';
import { formatDay, formatTime, formatTimeRange, localDate } from '../../lib/time';
import { useAvailabilityStore } from '../../stores/StoreContext';

/** One three-state answer per shift of a week, saved together (product-definition §5.1). */
export const AvailabilityForm = observer(function AvailabilityForm() {
  const store = useAvailabilityStore();

  useEffect(() => {
    void store.loadWeek(store.weekStart);
  }, [store]);

  async function save() {
    if (await store.save()) {
      notifications.show({
        color: 'success',
        title: 'Saved',
        message: 'Your availability was saved.',
      });
    }
  }

  const days = new Map<string, typeof store.rows>();
  for (const row of store.rows) {
    const date = localDate(row.shift.starts_at);
    days.set(date, [...(days.get(date) ?? []), row]);
  }

  let body;
  if (store.status === 'idle' || store.status === 'loading') {
    body = <LoadingState rows={3} />;
  } else if (store.status === 'error') {
    body = <ErrorState message={store.error ?? ''} onRetry={() => void store.reload()} />;
  } else if (store.rows.length === 0) {
    body = (
      <EmptyState
        icon={IconCalendarOff}
        title="No shifts for this week yet"
        description="Your manager has not created the shifts for this week. Check back later."
      />
    );
  } else {
    body = (
      <Stack gap="lg">
        {store.readOnlyReason ? (
          <Alert color="info" icon={<IconInfoCircle size={18} />} title="Read only">
            {store.readOnlyReason}
          </Alert>
        ) : (
          <Text c="ink.6">
            Choose when you can work. A shift you do not answer counts as unavailable.
          </Text>
        )}
        {[...days.entries()].map(([date, rows]) => (
          <Stack key={date} gap="sm" component="section" aria-label={formatDay(date)}>
            <Title order={3}>{formatDay(date)}</Title>
            {rows.map(({ shift, status }) => (
              <Card key={shift.id} padding="md">
                <Stack gap="sm">
                  <Stack gap={0}>
                    <Text fw={500}>{shift.name}</Text>
                    <Text size="sm" c="ink.6" className="tabular">
                      {formatTimeRange(shift.starts_at, shift.ends_at)}
                    </Text>
                  </Stack>
                  <AvailabilityControl
                    label={`Availability for ${formatDay(date)} ${formatTime(shift.starts_at)} ${shift.name}`}
                    value={status}
                    disabled={store.isReadOnly}
                    onChange={(next) => store.setAnswer(shift.id, next)}
                  />
                </Stack>
              </Card>
            ))}
          </Stack>
        ))}
        {store.saveError ? (
          <Alert color="danger" icon={<IconAlertCircle size={18} />} role="alert">
            {store.saveError}
          </Alert>
        ) : null}
        {store.isReadOnly ? null : (
          <Button
            fullWidth
            loading={store.isSaving}
            disabled={!store.isDirty}
            onClick={() => void save()}
          >
            Save availability
          </Button>
        )}
      </Stack>
    );
  }

  return (
    <Stack gap="lg">
      <Title order={1}>Availability</Title>
      <WeekNavigator
        weekStart={store.weekStart}
        disabled={store.isDirty}
        onPrevious={() => void store.goToWeek(-1)}
        onNext={() => void store.goToWeek(1)}
      />
      {store.isDirty ? (
        <Text size="sm" c="ink.6">
          You have unsaved changes. Save them to move to another week.
        </Text>
      ) : null}
      {body}
    </Stack>
  );
});
