import { Box, Button, Group, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconCalendarOff, IconPlayerPlay, IconSend } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useEffect, useState } from 'react';

import type { Assignment } from '../../api/types/schedule';
import { ConfirmDialog } from '../../components/ConfirmDialog';
import { EmptyState, ErrorState, LoadingState } from '../../components/StateViews';
import { ScheduleStatusBadge } from '../../components/StatusBadge';
import { WeekNavigator } from '../../components/WeekNavigator';
import {
  addDays,
  currentWeekStart,
  formatDay,
  formatWeekRange,
  localDate,
  localToday,
  shiftWeek,
} from '../../lib/time';
import type { ActionResult, ShiftEntry } from '../../stores/ScheduleStore';
import { useScheduleStore } from '../../stores/StoreContext';
import { AssignDialog } from './AssignDialog';
import { ShiftCard } from './ShiftCard';
import { UnfilledPanel } from './UnfilledPanel';

type Target =
  | { kind: 'add'; entry: ShiftEntry }
  | { kind: 'replace'; entry: ShiftEntry; assignment: Assignment }
  | { kind: 'remove'; entry: ShiftEntry; assignment: Assignment };

const DAYS_IN_WEEK = 7;

function describe(entry: ShiftEntry): string {
  return `${entry.shift.name} on ${formatDay(localDate(entry.shift.starts_at))}`;
}

/** Edits that bent a rule were saved; the server's warnings still deserve to be seen. */
function showWarnings(result: ActionResult) {
  if (!result.ok) return;
  for (const warning of result.warnings) {
    notifications.show({
      color: 'warning',
      title: 'Saved with a warning',
      message: warning.message,
      autoClose: false,
    });
  }
}

function showFailure(result: ActionResult) {
  if (result.ok) return;
  notifications.show({ color: 'danger', title: 'Could not do that', message: result.message });
}

/** The manager's week: shifts by day, generate, edit, publish (product-definition §5.2). */
export const ScheduleBoard = observer(function ScheduleBoard() {
  const store = useScheduleStore();
  const [target, setTarget] = useState<Target | null>(null);
  const [confirmingPublish, setConfirmingPublish] = useState(false);
  const [confirmingGenerate, setConfirmingGenerate] = useState(false);

  useEffect(() => {
    // The week being scheduled is next week.
    void store.loadBoard(shiftWeek(currentWeekStart(), 1));
    void store.loadEmployees();
  }, [store]);

  async function createShifts() {
    const result = await store.createShifts();
    showFailure(result);
    if (result.ok) {
      notifications.show({
        color: 'success',
        title: 'Shifts created',
        message: formatWeekRange(store.weekStart),
      });
    }
  }

  async function generate() {
    const result = await store.generate();
    showFailure(result);
    if (result.ok) {
      notifications.show({
        color: 'success',
        title: 'Draft generated',
        message: 'Review it below, then publish.',
      });
    }
  }

  const hasAssignments = (store.schedule?.assignments.length ?? 0) > 0;
  const today = localToday();
  const week = Array.from({ length: DAYS_IN_WEEK }, (_, index) => addDays(store.weekStart, index));

  let body;
  if (store.status === 'idle' || store.status === 'loading') {
    body = <LoadingState rows={3} />;
  } else if (store.status === 'error') {
    body = <ErrorState message={store.error ?? ''} onRetry={() => void store.reload()} />;
  } else if (!store.hasShifts) {
    body = (
      <EmptyState
        icon={IconCalendarOff}
        title="No shifts for this week"
        description="Create the week's shifts from your active shift templates, then generate a schedule."
        action={
          <Button loading={store.isWorking} onClick={() => void createShifts()}>
            Create this week's shifts
          </Button>
        }
      />
    );
  } else {
    body = (
      <Box style={{ overflowX: 'auto' }} pb="xs">
        <SimpleGrid
          cols={DAYS_IN_WEEK}
          spacing="sm"
          style={{ gridTemplateColumns: `repeat(${DAYS_IN_WEEK}, minmax(146px, 1fr))` }}
        >
          {week.map((date) => {
            const entries = store.days.find((day) => day.date === date)?.shifts ?? [];
            return (
              <Stack key={date} gap="sm" component="section" aria-label={formatDay(date)}>
                <Box
                  bg={date === today ? 'shibutzim.1' : 'sand.2'}
                  px="sm"
                  py={6}
                  style={{ borderRadius: 'var(--mantine-radius-md)' }}
                >
                  <Text fw={500} size="sm">
                    {formatDay(date)}
                  </Text>
                </Box>
                {entries.length === 0 ? (
                  <Text size="sm" c="ink.6" px="xs">
                    No shifts
                  </Text>
                ) : (
                  entries.map((entry) => (
                    <ShiftCard
                      key={entry.shift.shift_id}
                      entry={entry}
                      busy={store.isWorking}
                      onAdd={(next) => setTarget({ kind: 'add', entry: next })}
                      onReplace={(next, assignment) =>
                        setTarget({ kind: 'replace', entry: next, assignment })
                      }
                      onRemove={(next, assignment) =>
                        setTarget({ kind: 'remove', entry: next, assignment })
                      }
                    />
                  ))
                )}
              </Stack>
            );
          })}
        </SimpleGrid>
      </Box>
    );
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="center" wrap="wrap" gap="md">
        <Group gap="md">
          <Title order={1}>Schedule</Title>
          {store.status === 'loaded' ? <ScheduleStatusBadge status={store.scheduleStatus} /> : null}
        </Group>
        {store.status === 'loaded' && store.hasShifts ? (
          <Group gap="sm">
            <Button
              variant="outline"
              leftSection={<IconPlayerPlay size={18} />}
              disabled={!store.canGenerate}
              loading={store.isWorking}
              onClick={() => (hasAssignments ? setConfirmingGenerate(true) : void generate())}
            >
              Generate
            </Button>
            {store.scheduleStatus === 'draft' ? (
              <Button
                leftSection={<IconSend size={18} />}
                onClick={() => setConfirmingPublish(true)}
              >
                Publish
              </Button>
            ) : null}
          </Group>
        ) : null}
      </Group>

      <WeekNavigator
        weekStart={store.weekStart}
        onPrevious={() => void store.goToWeek(-1)}
        onNext={() => void store.goToWeek(1)}
        onToday={() => void store.loadBoard(currentWeekStart())}
      />

      {store.scheduleStatus === 'published' ? (
        <Text size="sm" c="ink.6">
          This schedule is published. Employees see every change at once, and Generate is off.
        </Text>
      ) : null}

      {store.lastRun ? <UnfilledPanel run={store.lastRun} /> : null}
      {body}

      <ConfirmDialog
        opened={confirmingGenerate}
        title="Replace the current draft?"
        message="Generate builds a new draft and replaces the one you have, including any edits you made."
        confirmLabel="Generate"
        onConfirm={async () => {
          const result = await store.generate();
          if (result.ok) {
            notifications.show({
              color: 'success',
              title: 'Draft generated',
              message: 'Review it below, then publish.',
            });
          }
          return result;
        }}
        onClose={() => setConfirmingGenerate(false)}
      />

      <ConfirmDialog
        opened={confirmingPublish}
        title="Publish the schedule?"
        message={`Publish the schedule for ${formatWeekRange(store.weekStart)}? Employees will see it immediately.`}
        confirmLabel="Publish"
        onConfirm={() => store.publish()}
        onSuccess={() =>
          notifications.show({
            color: 'success',
            title: 'Published',
            message: 'Employees can see the schedule now.',
          })
        }
        onClose={() => setConfirmingPublish(false)}
      />

      <AssignDialog
        opened={target?.kind === 'add'}
        title="Add someone"
        description={target?.kind === 'add' ? describe(target.entry) : ''}
        confirmLabel="Add"
        employees={store.employees}
        employeesError={store.employeesError}
        excludedUserIds={
          target?.kind === 'add' ? target.entry.people.map((person) => person.user_id) : []
        }
        onSubmit={(userId) =>
          target?.kind === 'add'
            ? store.addAssignment(target.entry.shift.shift_id, userId)
            : Promise.resolve<ActionResult>({
                ok: false,
                code: 'none',
                message: 'Nothing selected.',
              })
        }
        onSuccess={showWarnings}
        onClose={() => setTarget(null)}
      />

      <AssignDialog
        opened={target?.kind === 'replace'}
        title={target?.kind === 'replace' ? `Replace ${target.assignment.user_name}` : 'Replace'}
        description={target?.kind === 'replace' ? describe(target.entry) : ''}
        confirmLabel="Replace"
        employees={store.employees}
        employeesError={store.employeesError}
        excludedUserIds={
          target?.kind === 'replace' ? target.entry.people.map((person) => person.user_id) : []
        }
        onSubmit={(userId) =>
          target?.kind === 'replace'
            ? store.replaceAssignment(target.assignment.id, userId)
            : Promise.resolve<ActionResult>({
                ok: false,
                code: 'none',
                message: 'Nothing selected.',
              })
        }
        onSuccess={showWarnings}
        onClose={() => setTarget(null)}
      />

      <ConfirmDialog
        opened={target?.kind === 'remove'}
        title="Remove from the shift?"
        message={
          target?.kind === 'remove'
            ? `Remove ${target.assignment.user_name} from ${describe(target.entry)}?`
            : ''
        }
        confirmLabel="Remove"
        confirmColor="danger"
        onConfirm={() =>
          target?.kind === 'remove'
            ? store.removeAssignment(target.assignment.id)
            : Promise.resolve<ActionResult>({
                ok: false,
                code: 'none',
                message: 'Nothing selected.',
              })
        }
        onClose={() => setTarget(null)}
      />
    </Stack>
  );
});
