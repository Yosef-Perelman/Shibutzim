import { Alert, Button, Group, Modal, Stack, Text } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { useState } from 'react';

import type { ActionResult } from '../stores/ScheduleStore';

export interface ConfirmDialogProps {
  opened: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  /** `danger` for removing something; the default is the primary action. */
  confirmColor?: 'danger';
  /** Runs the action. A failure keeps the dialog open and shows the server's message inline. */
  onConfirm: () => Promise<ActionResult>;
  onClose: () => void;
  onSuccess?: (result: ActionResult & { ok: true }) => void;
}

/** Asks before a destructive or publishing action (ui-rules): Cancel, or the action itself. */
export function ConfirmDialog(props: ConfirmDialogProps) {
  const { opened, title, message, confirmLabel, confirmColor, onConfirm, onClose, onSuccess } =
    props;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    setError(null);
    onClose();
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    const result = await onConfirm();
    setBusy(false);
    if (result.ok) {
      onClose();
      onSuccess?.(result);
    } else {
      setError(result.message);
    }
  }

  return (
    <Modal opened={opened} onClose={close} title={title} centered>
      <Stack gap="lg">
        <Text>{message}</Text>
        {error ? (
          <Alert color="danger" icon={<IconAlertCircle size={18} />} role="alert">
            {error}
          </Alert>
        ) : null}
        <Group justify="flex-end">
          <Button variant="subtle" onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button color={confirmColor} loading={busy} onClick={() => void confirm()}>
            {confirmLabel}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
