import { Stack, Title } from '@mantine/core';
import { IconTools } from '@tabler/icons-react';

import { EmptyState } from './StateViews';

export interface ComingSoonProps {
  title: string;
}

/** Stands in for a screen that a later step of plan 003 builds. */
export function ComingSoon({ title }: ComingSoonProps) {
  return (
    <Stack gap="lg">
      <Title order={1}>{title}</Title>
      <EmptyState
        icon={IconTools}
        title="Coming soon"
        description="This screen is not built yet."
      />
    </Stack>
  );
}
