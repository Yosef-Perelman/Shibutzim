import {
  IconCalendarCheck,
  IconCalendarEvent,
  IconCoin,
  IconMessageCircle,
  IconUserPlus,
  IconUsers,
  type Icon,
} from '@tabler/icons-react';

export interface NavItem {
  to: string;
  label: string;
  icon: Icon;
}

export const EMPLOYEE_NAV: NavItem[] = [
  { to: '/me/shifts', label: 'Shifts', icon: IconCalendarEvent },
  { to: '/me/availability', label: 'Availability', icon: IconCalendarCheck },
  { to: '/me/pay', label: 'Pay', icon: IconCoin },
  { to: '/me/assistant', label: 'Assistant', icon: IconMessageCircle },
];

// A manager is never placed on a shift, so "My shifts" and "Availability" are for employees only.
export const MANAGER_NAV: NavItem[] = [
  { to: '/manager/schedule', label: 'Schedule', icon: IconCalendarEvent },
  { to: '/manager/team', label: 'Team', icon: IconUserPlus },
  { to: '/manager/pay', label: 'Team pay', icon: IconUsers },
  { to: '/me/pay', label: 'My pay', icon: IconCoin },
  { to: '/me/assistant', label: 'Assistant', icon: IconMessageCircle },
];
