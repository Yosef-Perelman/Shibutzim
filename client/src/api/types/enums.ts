// Mirrors server/app/core/enums.py; values are lowercase strings (glossary §1).

export type Role = 'manager' | 'employee';

export type AvailabilityStatus = 'available' | 'preferred' | 'unavailable';

export type ScheduleStatus = 'draft' | 'published';

export type TimeEntrySource = 'clock' | 'manual';
