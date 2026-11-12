import {
  Alert,
  Button,
  Group,
  Modal,
  PasswordInput,
  Select,
  Stack,
  TextInput,
} from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import { useState } from 'react';

import type { Role } from '../../api/types/enums';
import type { NewUser } from '../../api/types/user';
import type { ActionResult } from '../../stores/ScheduleStore';

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const RATE_PATTERN = /^\d{1,5}(\.\d{1,2})?$/;
const RATE_IS_ZERO = /^0+(\.0+)?$/;
const MAX_RATE_DIGITS = 5; // the server allows up to 10,000.00
const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_MAX_BYTES = 72; // what bcrypt can hash
const NAME_MAX_LENGTH = 120;
const EMAIL_TAKEN_CODE = 'email_already_used';

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'employee', label: 'Employee' },
  { value: 'manager', label: 'Manager' },
];

interface FieldErrors {
  name?: string;
  email?: string;
  hourlyRate?: string;
  password?: string;
}

/** The checks the server repeats; they only save a round trip and never replace the server's. */
export function validateNewPerson(values: {
  name: string;
  email: string;
  hourlyRate: string;
  password: string;
}): FieldErrors {
  const errors: FieldErrors = {};
  const name = values.name.trim();
  if (name.length === 0) errors.name = 'Enter a name.';
  else if (name.length > NAME_MAX_LENGTH)
    errors.name = `Use at most ${NAME_MAX_LENGTH} characters.`;
  if (!EMAIL_PATTERN.test(values.email.trim()))
    errors.email = 'Enter an email like name@example.com.';
  const rate = values.hourlyRate.trim();
  if (!RATE_PATTERN.test(rate) || RATE_IS_ZERO.test(rate)) {
    errors.hourlyRate = `Enter a rate above zero with up to two decimals, at most ${'9'.repeat(MAX_RATE_DIGITS)}.99.`;
  }
  if (values.password.length < PASSWORD_MIN_LENGTH) {
    errors.password = `Use at least ${PASSWORD_MIN_LENGTH} characters.`;
  } else if (new TextEncoder().encode(values.password).length > PASSWORD_MAX_BYTES) {
    errors.password = 'This password is too long.';
  }
  return errors;
}

export interface AddPersonDialogProps {
  opened: boolean;
  onSubmit: (person: NewUser) => Promise<ActionResult>;
  onClose: () => void;
  /** Called with the new person's name once the server accepted them. */
  onSuccess: (name: string) => void;
}

/** Adds an employee (or a manager) with an initial password the manager passes on. */
export function AddPersonDialog({ opened, onSubmit, onClose, onSuccess }: AddPersonDialogProps) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<Role>('employee');
  const [hourlyRate, setHourlyRate] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function reset() {
    setName('');
    setEmail('');
    setRole('employee');
    setHourlyRate('');
    setPassword('');
    setErrors({});
    setFormError(null);
  }

  function close() {
    reset();
    onClose();
  }

  async function submit() {
    const found = validateNewPerson({ name, email, hourlyRate, password });
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length > 0) return;

    setBusy(true);
    const person: NewUser = {
      name: name.trim(),
      email: email.trim(),
      role,
      hourly_rate: hourlyRate.trim(),
      password,
    };
    const result = await onSubmit(person);
    setBusy(false);
    if (result.ok) {
      reset();
      onClose();
      onSuccess(person.name);
    } else if (result.code === EMAIL_TAKEN_CODE) {
      setErrors({ email: result.message });
    } else {
      setFormError(result.message);
    }
  }

  return (
    <Modal opened={opened} onClose={close} title="Add a person" centered>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
        noValidate
      >
        <Stack gap="md">
          <TextInput
            label="Name"
            value={name}
            onChange={(event) => setName(event.currentTarget.value)}
            error={errors.name}
            data-autofocus
            required
          />
          <TextInput
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.currentTarget.value)}
            error={errors.email}
            required
          />
          <Select
            label="Role"
            data={ROLE_OPTIONS}
            value={role}
            onChange={(value) => setRole(value === 'manager' ? 'manager' : 'employee')}
            allowDeselect={false}
          />
          <TextInput
            label="Hourly rate (₪)"
            inputMode="decimal"
            value={hourlyRate}
            onChange={(event) => setHourlyRate(event.currentTarget.value)}
            error={errors.hourlyRate}
            required
          />
          <PasswordInput
            label="Initial password"
            description="At least 8 characters. Tell it to the person; they cannot change it yet."
            value={password}
            onChange={(event) => setPassword(event.currentTarget.value)}
            error={errors.password}
            autoComplete="new-password"
            required
          />
          {formError ? (
            <Alert color="danger" icon={<IconAlertCircle size={18} />} role="alert">
              {formError}
            </Alert>
          ) : null}
          <Group justify="flex-end">
            <Button variant="subtle" onClick={close} disabled={busy}>
              Cancel
            </Button>
            <Button type="submit" loading={busy}>
              Add person
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
