import {
  Alert,
  Box,
  Button,
  Card,
  Group,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconAlertCircle, IconInfoCircle } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useState, type FormEvent } from 'react';

import { useAuthStore } from '../../stores/StoreContext';

function labelOf(email: string): string {
  const name = email.split('@')[0] ?? email;
  return name.charAt(0).toUpperCase() + name.slice(1);
}

/** Email and password; shows the server's message verbatim and, in development, the demo accounts. */
export const LoginScreen = observer(function LoginScreen() {
  const auth = useAuthStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  function submit(event: FormEvent) {
    event.preventDefault();
    void auth.login(email, password);
  }

  return (
    <Box mih="100dvh" px="md" py="xl" style={{ display: 'flex', alignItems: 'center' }}>
      <Stack gap="lg" w="100%" maw={420} mx="auto">
        <Stack gap={4}>
          <Title order={1}>Shibutzim</Title>
          <Text c="ink.6">Sign in to see your shifts and pay.</Text>
        </Stack>

        {auth.sessionExpired ? (
          <Alert color="info" icon={<IconInfoCircle size={18} />} title="Session expired">
            Your session ended. Please sign in again.
          </Alert>
        ) : null}

        <Card component="form" onSubmit={submit} noValidate>
          <Stack gap="md">
            <TextInput
              label="Email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.currentTarget.value)}
              required
            />
            <PasswordInput
              label="Password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
              required
            />
            {auth.error ? (
              <Alert color="danger" icon={<IconAlertCircle size={18} />} role="alert">
                {auth.error}
              </Alert>
            ) : null}
            <Button type="submit" loading={auth.isBusy} fullWidth>
              Sign in
            </Button>
          </Stack>
        </Card>

        {auth.demoUsers.length > 0 ? (
          <Stack gap="xs">
            <Text size="sm" c="ink.6">
              Demo accounts: pick one, then type the demo password once.
            </Text>
            <Group gap="xs">
              {auth.demoUsers.map((demoEmail) => (
                <Button
                  key={demoEmail}
                  variant="light"
                  size="xs"
                  styles={{ root: { height: 36 } }}
                  onClick={() => setEmail(demoEmail)}
                >
                  {labelOf(demoEmail)}
                </Button>
              ))}
            </Group>
          </Stack>
        ) : null}
      </Stack>
    </Box>
  );
});
