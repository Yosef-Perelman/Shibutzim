import { Badge, Box, Container, Group, Menu, Text, UnstyledButton } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';
import { IconChevronDown, IconLogout, IconUser } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { Link, NavLink, Outlet } from 'react-router';

import { shadows } from '../../theme';
import { useAuthStore } from '../../stores/StoreContext';
import { EMPLOYEE_NAV, MANAGER_NAV, type NavItem } from './navigation';

const BOTTOM_BAR_HEIGHT = 64;

function linkStyle({ isActive }: { isActive: boolean }) {
  return {
    padding: '8px 4px',
    textDecoration: 'none',
    color: isActive ? 'var(--mantine-color-ink-9)' : 'var(--mantine-color-ink-6)',
    fontWeight: 500,
    borderBottom: `2px solid ${isActive ? 'var(--mantine-color-ink-9)' : 'transparent'}`,
  };
}

function TopNav({ items }: { items: NavItem[] }) {
  return (
    <Group component="nav" aria-label="Main" gap="lg" wrap="nowrap" style={{ overflowX: 'auto' }}>
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} style={linkStyle}>
          {item.label}
        </NavLink>
      ))}
    </Group>
  );
}

/** The employee's phone navigation: three items with icon and label, thumb height (design-system §6.4). */
function BottomBar({ items }: { items: NavItem[] }) {
  return (
    <Box
      component="nav"
      aria-label="Main"
      bg="white"
      style={{
        position: 'fixed',
        insetInline: 0,
        bottom: 0,
        zIndex: 10,
        display: 'flex',
        boxShadow: '0 -2px 8px rgba(31, 28, 66, 0.08)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
    >
      {items.map(({ to, label, icon: IconComponent }) => (
        <NavLink
          key={to}
          to={to}
          style={({ isActive }) => ({
            flex: 1,
            minHeight: BOTTOM_BAR_HEIGHT,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2,
            fontSize: 12,
            fontWeight: 500,
            textDecoration: 'none',
            color: isActive ? 'var(--mantine-color-shibutzim-6)' : 'var(--mantine-color-ink-6)',
          })}
        >
          <IconComponent size={22} aria-hidden />
          {label}
        </NavLink>
      ))}
    </Box>
  );
}

const UserMenu = observer(function UserMenu() {
  const auth = useAuthStore();
  const user = auth.user;
  if (!user) return null;
  return (
    <Menu position="bottom-end" width={240}>
      <Menu.Target>
        <UnstyledButton aria-label={`Account menu for ${user.name}`} mih={44}>
          <Group gap="xs" wrap="nowrap">
            <IconUser size={20} aria-hidden />
            <Text fw={500} visibleFrom="xs">
              {user.name}
            </Text>
            <Badge color="ink" variant="light" tt="capitalize" size="lg">
              {user.role}
            </Badge>
            <IconChevronDown size={16} aria-hidden />
          </Group>
        </UnstyledButton>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{user.email}</Menu.Label>
        {auth.demoUsers.length > 0 ? (
          <>
            <Menu.Label>Switch demo user</Menu.Label>
            {auth.demoUsers
              .filter((email) => email !== user.email)
              .map((email) => (
                <Menu.Item key={email} onClick={() => void auth.switchTo(email)}>
                  {email.split('@')[0]}
                </Menu.Item>
              ))}
            <Menu.Divider />
          </>
        ) : null}
        <Menu.Item leftSection={<IconLogout size={16} />} onClick={() => auth.logout()}>
          Log out
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
});

/** Header with the brand, the navigation of the role and the user menu; renders the routed screen. */
export const AppShell = observer(function AppShell() {
  const auth = useAuthStore();
  const isPhone = useMediaQuery('(max-width: 47.99em)') ?? false;
  const items = auth.isManager ? MANAGER_NAV : EMPLOYEE_NAV;
  const showBottomBar = !auth.isManager && isPhone;

  return (
    <>
      <Box
        component="header"
        bg="white"
        style={{ position: 'sticky', top: 0, zIndex: 10, boxShadow: shadows.header }}
      >
        <Container size="lg" h={56} px="md" style={{ display: 'flex', alignItems: 'center' }}>
          <Group justify="space-between" wrap="nowrap" w="100%" gap="lg">
            <Group gap="xl" wrap="nowrap">
              <Text component={Link} to={auth.homePath} fw={500} size="lg" c="ink.9" td="none">
                Shibutzim
              </Text>
              {showBottomBar ? null : <TopNav items={items} />}
            </Group>
            <UserMenu />
          </Group>
        </Container>
      </Box>
      <Container
        size={auth.isManager ? 'lg' : 640}
        px="md"
        pt="lg"
        pb={showBottomBar ? BOTTOM_BAR_HEIGHT + 24 : 'xl'}
        component="main"
      >
        <Outlet />
      </Container>
      {showBottomBar ? <BottomBar items={items} /> : null}
    </>
  );
});
