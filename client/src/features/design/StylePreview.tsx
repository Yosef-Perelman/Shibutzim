import {
  ActionIcon,
  Alert,
  Box,
  Button,
  Card,
  Container,
  Group,
  Modal,
  Paper,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconBell,
  IconCalendarEvent,
  IconCoin,
  IconInbox,
  IconTrash,
  IconUser,
} from '@tabler/icons-react';
import { useState } from 'react';

import type { AvailabilityStatus } from '../../api/types/enums';
import { AvailabilityControl } from '../../components/AvailabilityControl';
import { IconTile } from '../../components/IconTile';
import {
  AvailabilityBadge,
  CoverageBadge,
  ScheduleStatusBadge,
  ToneBadge,
} from '../../components/StatusBadge';
import { EmptyState, ErrorState, LoadingState } from '../../components/StateViews';
import { shadows, toneColors, type Tone } from '../../theme';
import {
  brandSwatches,
  neutralSwatches,
  radiusScale,
  spacingScale,
  typeScale,
  type Swatch,
} from './tokens';

interface SectionProps {
  title: string;
  children: React.ReactNode;
}

function Section({ title, children }: SectionProps) {
  return (
    <Stack gap="md" component="section">
      <Title order={2}>{title}</Title>
      {children}
    </Stack>
  );
}

function SwatchCard({ swatch }: { swatch: Swatch }) {
  return (
    <Card padding="md">
      <Group wrap="nowrap" gap="md" align="flex-start">
        <Box
          aria-hidden
          w={44}
          h={44}
          style={{
            flexShrink: 0,
            background: swatch.hex,
            borderRadius: 'var(--mantine-radius-md)',
            border: '1px solid var(--mantine-color-sand-3)',
          }}
        />
        <Stack gap={2}>
          <Text fw={500}>{swatch.name}</Text>
          <Text size="sm" c="ink.6" className="tabular">
            {swatch.hex}
          </Text>
          <Text size="sm" c="ink.6">
            {swatch.use}
          </Text>
          {swatch.contrast ? (
            <Text size="xs" c="ink.6">
              {swatch.contrast}
            </Text>
          ) : null}
        </Stack>
      </Group>
    </Card>
  );
}

const TONES: { tone: Tone; label: string }[] = [
  { tone: 'success', label: 'Success' },
  { tone: 'warning', label: 'Warning' },
  { tone: 'danger', label: 'Danger' },
  { tone: 'info', label: 'Info' },
  { tone: 'neutral', label: 'Neutral' },
  { tone: 'purple', label: 'Purple (preferred)' },
];

function ColorSection() {
  return (
    <Section title="Color">
      <Text c="ink.6">Neutrals</Text>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        {neutralSwatches.map((swatch) => (
          <SwatchCard key={swatch.name} swatch={swatch} />
        ))}
      </SimpleGrid>
      <Text c="ink.6">Brand and action</Text>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {brandSwatches.map((swatch) => (
          <SwatchCard key={swatch.name} swatch={swatch} />
        ))}
      </SimpleGrid>
      <Text c="ink.6">Status: text on fill, always with an icon and a word</Text>
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }}>
        {TONES.map(({ tone, label }) => (
          <Card key={tone} padding="md">
            <Group justify="space-between">
              <ToneBadge tone={tone} label={label} />
              <Text size="xs" c="ink.6" className="tabular">
                {toneColors[tone].text} on {toneColors[tone].fill}
              </Text>
            </Group>
          </Card>
        ))}
      </SimpleGrid>
    </Section>
  );
}

function TypographySection() {
  return (
    <Section title="Typography">
      <Card>
        <Stack gap="md">
          {typeScale.map((style) => (
            <Group key={style.role} align="baseline" wrap="nowrap" gap="lg">
              <Text size="xs" c="ink.6" w={72} style={{ flexShrink: 0 }}>
                {style.role}
                <br />
                {style.size}/{style.lineHeight}
              </Text>
              <Text
                style={{
                  fontSize: style.size,
                  lineHeight: `${style.lineHeight}px`,
                  fontWeight: style.weight,
                }}
              >
                {style.sample}
              </Text>
            </Group>
          ))}
        </Stack>
      </Card>
    </Section>
  );
}

function ShapeSection() {
  return (
    <Section title="Spacing, radius and elevation">
      <Card>
        <Stack gap="sm">
          {spacingScale.map(({ name, px }) => (
            <Group key={name} gap="md" wrap="nowrap">
              <Text size="sm" w={48} className="tabular">
                {name}
              </Text>
              <Box h={12} w={px} bg="shibutzim.6" style={{ borderRadius: 4 }} />
              <Text size="sm" c="ink.6">
                {px}px
              </Text>
            </Group>
          ))}
        </Stack>
      </Card>
      <SimpleGrid cols={{ base: 2, sm: 4 }}>
        {radiusScale.map(({ name, px, use }) => (
          <Stack key={name} gap="xs" align="flex-start">
            <Box
              w={80}
              h={80}
              bg="sand.1"
              style={{
                borderRadius: px,
                border: '1px solid var(--mantine-color-sand-3)',
              }}
            />
            <Text size="sm" fw={500}>
              {name} · {px === 999 ? 'pill' : `${px}px`}
            </Text>
            <Text size="xs" c="ink.6">
              {use}
            </Text>
          </Stack>
        ))}
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <Paper p="lg" bg="white" style={{ boxShadow: shadows.header }}>
          <Text fw={500}>shadow-header</Text>
          <Text size="sm" c="ink.6">
            sticky header and bottom bar
          </Text>
        </Paper>
        <Paper p="lg" bg="white" style={{ boxShadow: shadows.overlay }}>
          <Text fw={500}>shadow-overlay</Text>
          <Text size="sm" c="ink.6">
            dialogs, menus, notifications
          </Text>
        </Paper>
      </SimpleGrid>
    </Section>
  );
}

function ButtonSection() {
  const [loading, setLoading] = useState(false);
  return (
    <Section title="Buttons">
      <Card>
        <Stack gap="md">
          <Group>
            <Button>Primary</Button>
            <Button variant="outline">Secondary</Button>
            <Button variant="subtle">Subtle</Button>
            <Button color="danger">Danger</Button>
          </Group>
          <Group>
            <Button
              loading={loading}
              onClick={() => {
                setLoading(true);
                window.setTimeout(() => setLoading(false), 1500);
              }}
            >
              Click to load
            </Button>
            <Button disabled>Disabled</Button>
            <ActionIcon variant="subtle" size={44} radius="xl" aria-label="Remove assignment">
              <IconTrash size={20} />
            </ActionIcon>
            <ActionIcon variant="subtle" size={44} radius="xl" aria-label="Notifications">
              <IconBell size={20} />
            </ActionIcon>
          </Group>
        </Stack>
      </Card>
    </Section>
  );
}

function FormSection() {
  const [status, setStatus] = useState<AvailabilityStatus>('available');
  const [preferred, setPreferred] = useState<AvailabilityStatus>('preferred');
  const [unavailable, setUnavailable] = useState<AvailabilityStatus>('unavailable');
  return (
    <Section title="Inputs and the availability control">
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card>
          <Stack gap="md">
            <TextInput
              label="Email"
              description="Use your work email"
              placeholder="you@example.com"
            />
            <TextInput
              label="Password"
              type="password"
              defaultValue="wrong"
              error="Email or password is incorrect."
            />
            <TextInput label="Disabled" disabled defaultValue="Locked week" />
          </Stack>
        </Card>
        <Card>
          <Stack gap="md">
            <Text fw={500}>Sun 07:00–15:00 · Morning</Text>
            <AvailabilityControl
              label="Availability, available"
              value={status}
              onChange={setStatus}
            />
            <AvailabilityControl
              label="Availability, preferred"
              value={preferred}
              onChange={setPreferred}
            />
            <AvailabilityControl
              label="Availability, unavailable"
              value={unavailable}
              onChange={setUnavailable}
            />
            <AvailabilityControl
              label="Availability, locked"
              value="available"
              onChange={() => undefined}
              disabled
            />
          </Stack>
        </Card>
      </SimpleGrid>
    </Section>
  );
}

function BadgeSection() {
  return (
    <Section title="Badges">
      <Card>
        <Stack gap="md">
          <Group>
            <AvailabilityBadge status="available" />
            <AvailabilityBadge status="preferred" />
            <AvailabilityBadge status="unavailable" />
          </Group>
          <Group>
            <ScheduleStatusBadge status={null} />
            <ScheduleStatusBadge status="draft" />
            <ScheduleStatusBadge status="published" />
          </Group>
          <Group>
            <CoverageBadge assigned={3} required={3} />
            <CoverageBadge assigned={2} required={3} />
          </Group>
        </Stack>
      </Card>
    </Section>
  );
}

const PAY_ROWS = [
  { day: 'Sun 8 Nov', hours: '9.00', amount: '₪391.00' },
  { day: 'Mon 9 Nov', hours: '8.00', amount: '₪340.00' },
  { day: 'Tue 10 Nov', hours: '10.50', amount: '₪482.50' },
];

function CardSection() {
  return (
    <Section title="Cards, tabs and tables">
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card>
          <Stack gap="md">
            <Group justify="space-between" wrap="nowrap">
              <Group wrap="nowrap" gap="md">
                <IconTile icon={IconCalendarEvent} />
                <Stack gap={0}>
                  <Title order={3}>Morning</Title>
                  <Text size="sm" c="ink.6" className="tabular">
                    Sun 07:00–15:00
                  </Text>
                </Stack>
              </Group>
              <CoverageBadge assigned={2} required={3} />
            </Group>
            <Text size="sm">Noa Katz · Omer Barak</Text>
          </Stack>
        </Card>
        <Card bg="shibutzim.1">
          <Group wrap="nowrap" gap="md">
            <IconTile icon={IconUser} size={32} />
            <Stack gap={0}>
              <Text fw={500}>You · Evening</Text>
              <Text size="sm" c="ink.6" className="tabular">
                Mon 16:00–23:00
              </Text>
            </Stack>
          </Group>
        </Card>
      </SimpleGrid>
      <Tabs defaultValue="week">
        <Tabs.List>
          <Tabs.Tab value="week">This week</Tabs.Tab>
          <Tabs.Tab value="next">Next week</Tabs.Tab>
          <Tabs.Tab value="past">Past</Tabs.Tab>
        </Tabs.List>
      </Tabs>
      <Card padding="0" style={{ overflowX: 'auto' }}>
        <Table>
          <Table.Thead bg="sand.2">
            <Table.Tr>
              <Table.Th>Work day</Table.Th>
              <Table.Th ta="right">Hours</Table.Th>
              <Table.Th ta="right">Amount</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {PAY_ROWS.map((row) => (
              <Table.Tr key={row.day}>
                <Table.Td>{row.day}</Table.Td>
                <Table.Td ta="right" className="tabular">
                  {row.hours}
                </Table.Td>
                <Table.Td ta="right" className="tabular">
                  {row.amount}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
          <Table.Tfoot>
            <Table.Tr fw={500}>
              <Table.Td>Total</Table.Td>
              <Table.Td ta="right" className="tabular">
                27.50
              </Table.Td>
              <Table.Td ta="right" className="tabular">
                ₪1,213.50
              </Table.Td>
            </Table.Tr>
          </Table.Tfoot>
        </Table>
      </Card>
    </Section>
  );
}

function StatesSection() {
  return (
    <Section title="Loading, empty and error states">
      <SimpleGrid cols={{ base: 1, md: 3 }}>
        <Stack gap="sm">
          <Text size="sm" c="ink.6">
            Loading
          </Text>
          <LoadingState rows={2} />
        </Stack>
        <Card>
          <Text size="sm" c="ink.6">
            Empty
          </Text>
          <EmptyState
            icon={IconInbox}
            title="Schedule not published yet"
            description="Your manager has not published this week. You will see your shifts here once they do."
          />
        </Card>
        <Stack gap="sm">
          <Text size="sm" c="ink.6">
            Error
          </Text>
          <ErrorState message="Something went wrong on our side." onRetry={() => undefined} />
        </Stack>
      </SimpleGrid>
    </Section>
  );
}

function OverlaySection() {
  const [open, setOpen] = useState(false);
  return (
    <Section title="Dialog and notifications">
      <Card>
        <Group>
          <Button variant="outline" onClick={() => setOpen(true)}>
            Open the publish dialog
          </Button>
          <Button
            variant="subtle"
            onClick={() =>
              notifications.show({
                title: 'Saved',
                message: 'Your availability was saved.',
                color: 'success',
              })
            }
          >
            Success toast
          </Button>
          <Button
            variant="subtle"
            onClick={() =>
              notifications.show({
                title: 'Heads up',
                message: 'Dana marked this shift as unavailable.',
                color: 'warning',
                autoClose: false,
              })
            }
          >
            Warning toast
          </Button>
        </Group>
      </Card>
      <Modal opened={open} onClose={() => setOpen(false)} title="Publish the schedule?" centered>
        <Stack gap="lg">
          <Text>Publish the schedule for 15–21 Nov? Employees will see it immediately.</Text>
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => setOpen(false)}>Publish</Button>
          </Group>
        </Stack>
      </Modal>
      <Alert color="info" title="Reading this page" icon={<IconCoin size={18} />}>
        Check it at 375 px (phone) and 1280 px (desktop). Reference: docs/design-system.md.
      </Alert>
    </Section>
  );
}

/** A development-only page that shows every token and component state of the design system. */
export function StylePreview() {
  return (
    <>
      <Box
        component="header"
        bg="white"
        px="md"
        h={56}
        style={{
          boxShadow: shadows.header,
          display: 'flex',
          alignItems: 'center',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <Text fw={500} size="lg">
          Shibutzim · style preview
        </Text>
      </Box>
      <Container size="lg" py="xl">
        <Stack gap="xl">
          <Title order={1}>Style preview</Title>
          <ColorSection />
          <TypographySection />
          <ShapeSection />
          <ButtonSection />
          <FormSection />
          <BadgeSection />
          <CardSection />
          <StatesSection />
          <OverlaySection />
        </Stack>
      </Container>
    </>
  );
}
