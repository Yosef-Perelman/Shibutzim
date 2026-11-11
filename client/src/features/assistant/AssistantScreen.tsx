import {
  Badge,
  Button,
  Card,
  Group,
  Paper,
  Skeleton,
  Stack,
  Text,
  Textarea,
  Title,
} from '@mantine/core';
import { IconBook, IconMessageCircle, IconSend } from '@tabler/icons-react';
import { observer } from 'mobx-react-lite';
import { useEffect, useRef, useState } from 'react';

import { EmptyState, ErrorState } from '../../components/StateViews';
import type { ChatEntry } from '../../stores/AssistantStore';
import { useAssistantStore, useAuthStore } from '../../stores/StoreContext';
import { ProposalCard } from './ProposalCard';
import { lookedAt } from './toolLabels';

const MAX_CHARACTERS = 2000;
const EMPLOYEE_QUESTIONS = [
  'How many hours did I work this month?',
  'Am I allowed to swap a shift?',
  'Why is my pay lower than last month?',
];
const MANAGER_QUESTIONS = [
  'Who can work next Monday morning?',
  "Build next week's schedule",
  'How many hours did the team work this month?',
];

function UserMessage({ entry }: { entry: ChatEntry }) {
  return (
    <Group justify="flex-end">
      <Paper bg="shibutzim.1" p="md" radius="lg" maw="85%">
        <Text size="xs" c="ink.6" fw={500}>
          You
        </Text>
        <Text style={{ whiteSpace: 'pre-wrap' }}>{entry.content}</Text>
      </Paper>
    </Group>
  );
}

function AssistantMessage({ entry }: { entry: ChatEntry }) {
  const looked = lookedAt(entry.toolCalls.map((call) => call.name));
  return (
    <Stack gap="sm" maw="95%">
      <Card padding="md">
        <Stack gap="xs">
          <Text size="xs" c="ink.6" fw={500}>
            Assistant
          </Text>
          <Text style={{ whiteSpace: 'pre-wrap' }}>{entry.content}</Text>
          {entry.citations.length > 0 ? (
            <Group gap="xs">
              {entry.citations.map((title) => (
                <Badge key={title} variant="light" size="lg" leftSection={<IconBook size={14} />}>
                  Handbook: {title}
                </Badge>
              ))}
            </Group>
          ) : null}
          {looked.length > 0 ? (
            <Text size="xs" c="ink.6">
              Looked at: {looked.join(', ')}
            </Text>
          ) : null}
        </Stack>
      </Card>
      {entry.proposal ? <ProposalCard entry={entry} /> : null}
    </Stack>
  );
}

function Thinking() {
  return (
    <Card padding="md" role="status" aria-live="polite">
      <Stack gap="xs">
        <Text c="ink.6">Thinking…</Text>
        <Skeleton height={12} width="70%" radius="xl" />
        <Skeleton height={12} width="45%" radius="xl" />
      </Stack>
    </Card>
  );
}

/** The chat for every signed-in person: it asks the server, which runs tools as this user. */
export const AssistantScreen = observer(function AssistantScreen() {
  const store = useAssistantStore();
  const auth = useAuthStore();
  const [draft, setDraft] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  const questions = auth.isManager ? MANAGER_QUESTIONS : EMPLOYEE_QUESTIONS;

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' });
  }, [store.messages.length, store.isSending]);

  async function submit(text: string) {
    if (store.isSending || !text.trim()) return;
    setDraft('');
    await store.send(text);
  }

  return (
    <Stack gap="lg">
      <Group justify="space-between" align="center" wrap="nowrap">
        <Title order={1}>Assistant</Title>
        {store.messages.length > 0 ? (
          <Button variant="subtle" onClick={() => store.reset()}>
            New conversation
          </Button>
        ) : null}
      </Group>

      {store.messages.length === 0 ? (
        <EmptyState
          icon={IconMessageCircle}
          title="Ask about your work"
          description={
            auth.isManager
              ? "Who is available, the team's hours, the company policy and next week's schedule. I look things up and never guess numbers."
              : 'Your shifts, hours, pay and the company policy. I look things up and never guess numbers.'
          }
          action={
            <Stack gap="sm" align="stretch" w="100%" maw={420}>
              {questions.map((question) => (
                <Button key={question} variant="outline" onClick={() => void submit(question)}>
                  {question}
                </Button>
              ))}
            </Stack>
          }
        />
      ) : (
        <Stack gap="md" role="log" aria-label="Conversation" aria-live="polite">
          {store.messages.map((entry) =>
            entry.role === 'user' ? (
              <UserMessage key={entry.id} entry={entry} />
            ) : (
              <AssistantMessage key={entry.id} entry={entry} />
            ),
          )}
        </Stack>
      )}

      {store.isSending ? <Thinking /> : null}
      {store.error ? (
        <ErrorState
          message={store.error}
          onRetry={store.canRetry ? () => void store.retry() : undefined}
        />
      ) : null}

      <Group align="flex-end" wrap="nowrap" gap="sm">
        <Textarea
          label="Your question"
          style={{ flex: 1 }}
          rows={2}
          maxLength={MAX_CHARACTERS}
          value={draft}
          onChange={(event) => setDraft(event.currentTarget.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              void submit(draft);
            }
          }}
        />
        <Button
          leftSection={<IconSend size={18} />}
          disabled={store.isSending}
          onClick={() => void submit(draft)}
        >
          Send
        </Button>
      </Group>
      <div ref={endRef} />
    </Stack>
  );
});
