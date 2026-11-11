import { Box } from '@mantine/core';
import type { Icon } from '@tabler/icons-react';

export interface IconTileProps {
  icon: Icon;
  /** 44 for a card header (default), 32 for inline use. */
  size?: 32 | 44;
}

/** A navy rounded square with a white icon: the type marker of a card (design-system §6.3). */
export function IconTile({ icon: IconComponent, size = 44 }: IconTileProps) {
  return (
    <Box
      aria-hidden
      w={size}
      h={size}
      bg="ink.9"
      c="white"
      style={{
        borderRadius: 'var(--mantine-radius-md)',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <IconComponent size={size === 44 ? 24 : 18} stroke={1.75} />
    </Box>
  );
}
