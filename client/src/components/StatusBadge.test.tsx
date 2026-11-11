import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { theme } from '../theme';
import { AvailabilityBadge, CoverageBadge, ScheduleStatusBadge } from './StatusBadge';

function renderWithTheme(node: React.ReactNode) {
  return render(<MantineProvider theme={theme}>{node}</MantineProvider>);
}

describe('status badges', () => {
  it('names each availability status with a word, not only a color', () => {
    renderWithTheme(
      <>
        <AvailabilityBadge status="available" />
        <AvailabilityBadge status="preferred" />
        <AvailabilityBadge status="unavailable" />
      </>,
    );
    expect(screen.getByText('Available')).toBeInTheDocument();
    expect(screen.getByText('Preferred')).toBeInTheDocument();
    expect(screen.getByText('Unavailable')).toBeInTheDocument();
  });

  it('says "No schedule" when a week has no schedule', () => {
    renderWithTheme(<ScheduleStatusBadge status={null} />);
    expect(screen.getByText('No schedule')).toBeInTheDocument();
  });

  it('shows assigned over required for a short shift', () => {
    renderWithTheme(<CoverageBadge assigned={2} required={3} />);
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
  });
});
