import { Button, Card, Group, Skeleton, Stack, Text, Title } from '@mantine/core';
import { IconAlertCircle, type Icon } from '@tabler/icons-react';
import type { ReactNode } from 'react';

import { IconTile } from './IconTile';

export interface LoadingStateProps {
  /** How many card-shaped skeletons to show. */
  rows?: number;
}

/** Skeletons in the shape of the final content; never a full-page spinner (design-system §6.5). */
export function LoadingState({ rows = 3 }: LoadingStateProps) {
  return (
    <Stack gap="md" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} height={88} radius="lg" />
      ))}
    </Stack>
  );
}

export interface EmptyStateProps {
  icon: Icon;
  title: string;
  description?: string;
  action?: ReactNode;
}

/** Says what is missing and why, and offers the action if there is one. */
export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <Stack align="center" gap="sm" py="xl" ta="center">
      <IconTile icon={icon} />
      <Title order={3}>{title}</Title>
      {description ? (
        <Text c="ink.6" maw={420}>
          {description}
        </Text>
      ) : null}
      {action}
    </Stack>
  );
}

export interface ErrorStateProps {
  /** The server's `error.message`, shown as it is. */
  message: string;
  onRetry?: () => void;
}

/** A danger card with the message and a Retry button; never a blank page. */
export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <Card role="alert" bg="danger.1">
      <Group align="flex-start" wrap="nowrap" gap="md">
        <IconAlertCircle size={24} color="var(--mantine-color-danger-6)" aria-hidden />
        <Stack gap="sm" align="flex-start">
          <Text c="danger.6" fw={500}>
            {message}
          </Text>
          {onRetry ? (
            <Button variant="outline" color="danger" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </Stack>
      </Group>
    </Card>
  );
}
