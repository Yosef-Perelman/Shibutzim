import { Card, Group, Stack, Text, Title } from '@mantine/core';
import { IconCalendarOff, IconUser } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useEffect } from 'react';

import { EmptyState, ErrorState, LoadingState } from '../../components/StateViews';
import { IconTile } from '../../components/IconTile';
import { WeekNavigator } from '../../components/WeekNavigator';
import { currentWeekStart, formatDay, formatTimeRange, localDate } from '../../lib/time';
import type { ShiftEntry } from '../../stores/ScheduleStore';
import { useAuthStore, useScheduleStore } from '../../stores/StoreContext';

interface ShiftRowProps {
  entry: ShiftEntry;
  currentUserId: number | null;
  /** Show the day in the card (own shifts are listed without day headings). */
  showDay?: boolean;
}

function ShiftRow({ entry, currentUserId, showDay }: ShiftRowProps) {
  const { shift, people, isMine } = entry;
  const names = people.map((person) =>
    person.user_id === currentUserId ? 'You' : person.user_name,
  );
  return (
    <Card
      bg={isMine ? 'shibutzim.1' : undefined}
      padding="md"
      component="li"
      style={{ listStyle: 'none' }}
    >
      <Group wrap="nowrap" gap="md" align="flex-start">
        {isMine ? <IconTile icon={IconUser} size={32} /> : null}
        <Stack gap={2}>
          <Text fw={500}>
            {showDay ? `${formatDay(localDate(shift.starts_at))} · ` : ''}
            {shift.name}
          </Text>
          <Text size="sm" c="ink.6" className="tabular">
            {formatTimeRange(shift.starts_at, shift.ends_at)}
          </Text>
          <Text size="sm">{names.length > 0 ? names.join(', ') : 'Nobody assigned yet'}</Text>
        </Stack>
      </Group>
    </Card>
  );
}

/** The published schedule of a week: own shifts first, then the whole team by day. */
export const MyShifts = observer(function MyShifts() {
  const store = useScheduleStore();
  const auth = useAuthStore();
  const currentUserId = auth.user?.id ?? null;

  useEffect(() => {
    void store.loadWeek(currentWeekStart());
  }, [store]);

  let body;
  if (store.status === 'idle' || store.status === 'loading') {
    body = <LoadingState rows={3} />;
  } else if (store.status === 'error') {
    body = <ErrorState message={store.error ?? ''} onRetry={() => void store.reload()} />;
  } else if (!store.hasSchedule) {
    body = (
      <EmptyState
        icon={IconCalendarOff}
        title="Schedule not published yet"
        description="Your manager has not published this week. You will see your shifts here once they do."
      />
    );
  } else {
    body = (
      <Stack gap="xl">
        <Stack gap="sm" component="section" aria-labelledby="own-shifts">
          <Title order={2} id="own-shifts">
            Your shifts
          </Title>
          {store.mine.length === 0 ? (
            <Text c="ink.6">You have no shifts this week.</Text>
          ) : (
            <Stack gap="sm" component="ul" p={0} m={0}>
              {store.mine.map((entry) => (
                <ShiftRow
                  key={entry.shift.shift_id}
                  entry={entry}
                  currentUserId={currentUserId}
                  showDay
                />
              ))}
            </Stack>
          )}
        </Stack>
        <Stack gap="md" component="section" aria-labelledby="team-shifts">
          <Title order={2} id="team-shifts">
            Whole team
          </Title>
          {store.days.map((day) => (
            <Stack key={day.date} gap="sm">
              <Title order={3}>{formatDay(day.date)}</Title>
              <Stack gap="sm" component="ul" p={0} m={0}>
                {day.shifts.map((entry) => (
                  <ShiftRow
                    key={entry.shift.shift_id}
                    entry={entry}
                    currentUserId={currentUserId}
                  />
                ))}
              </Stack>
            </Stack>
          ))}
        </Stack>
      </Stack>
    );
  }

  return (
    <Stack gap="lg">
      <Title order={1}>My shifts</Title>
      <WeekNavigator
        weekStart={store.weekStart}
        onPrevious={() => void store.goToWeek(-1)}
        onNext={() => void store.goToWeek(1)}
        onToday={() => void store.loadWeek(currentWeekStart())}
      />
      {body}
    </Stack>
  );
});
