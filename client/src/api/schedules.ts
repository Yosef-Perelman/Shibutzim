import type { ApiClient } from './apiClient';
import type {
  AssignmentCreate,
  AssignmentEditOut,
  AssignmentUpdate,
  Schedule,
  ScheduleGenerateIn,
  ScheduleGenerateOut,
} from './types/schedule';

export function createSchedulesApi(client: ApiClient) {
  const base = (week_start: string) => `/api/schedules/${week_start}`;
  return {
    get: (week_start: string) => client.get<Schedule>(base(week_start)),
    generate: (week_start: string, body?: ScheduleGenerateIn) =>
      client.post<ScheduleGenerateOut>(`${base(week_start)}/generate`, body),
    publish: (week_start: string) => client.post<Schedule>(`${base(week_start)}/publish`),
    addAssignment: (week_start: string, body: AssignmentCreate) =>
      client.post<AssignmentEditOut>(`${base(week_start)}/assignments`, body),
    replaceAssignment: (week_start: string, assignment_id: number, body: AssignmentUpdate) =>
      client.patch<AssignmentEditOut>(`${base(week_start)}/assignments/${assignment_id}`, body),
    removeAssignment: (week_start: string, assignment_id: number) =>
      client.delete(`${base(week_start)}/assignments/${assignment_id}`),
  };
}
