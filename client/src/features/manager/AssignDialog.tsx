import { Alert, Button, Group, Modal, Select, Stack, Text } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { useState } from 'react';

import type { User } from '../../api/types/user';
import type { ActionResult } from '../../stores/ScheduleStore';

export interface AssignDialogProps {
  opened: boolean;
  title: string;
  /** What the choice is about, e.g. "Morning on Sun 15 Nov". */
  description: string;
  confirmLabel: string;
  employees: User[];
  /** Employees to leave out of the list, e.g. those already on the shift. */
  excludedUserIds?: number[];
  /** Why the list may be empty or incomplete (the employee list failed to load). */
  employeesError?: string | null;
  onSubmit: (userId: number) => Promise<ActionResult>;
  onClose: () => void;
  onSuccess: (result: ActionResult & { ok: true }) => void;
}

/** Pick an employee for a shift (add) or to take over an assignment (replace). */
export function AssignDialog(props: AssignDialogProps) {
  const { opened, title, description, confirmLabel, employees, excludedUserIds = [] } = props;
  const { employeesError, onSubmit, onClose, onSuccess } = props;
  const [userId, setUserId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const options = employees
    .filter((employee) => !excludedUserIds.includes(employee.id))
    .map((employee) => ({ value: String(employee.id), label: employee.name }));

  function close() {
    setUserId(null);
    setError(null);
    onClose();
  }

  async function submit() {
    if (userId === null) return;
    setBusy(true);
    setError(null);
    const result = await onSubmit(Number(userId));
    setBusy(false);
    if (result.ok) {
      setUserId(null);
      onClose();
      onSuccess(result);
    } else {
      setError(result.message);
    }
  }

  return (
    <Modal opened={opened} onClose={close} title={title} centered>
      <Stack gap="lg">
        <Text c="ink.6">{description}</Text>
        <Select
          label="Employee"
          placeholder="Choose an employee"
          data={options}
          value={userId}
          onChange={setUserId}
          searchable
          nothingFoundMessage="No employees to choose from"
          error={employeesError ?? undefined}
        />
        {error ? (
          <Alert color="danger" icon={<IconAlertCircle size={18} />} role="alert">
            {error}
          </Alert>
        ) : null}
        <Group justify="flex-end">
          <Button variant="subtle" onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button loading={busy} disabled={userId === null} onClick={() => void submit()}>
            {confirmLabel}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
