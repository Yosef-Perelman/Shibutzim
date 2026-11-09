# UI rules

React + Vite + TypeScript + MobX + Mantine. Architecture in
[architecture.md §9](../architecture.md#9-client-architecture).

## State and data

- One MobX store per domain (`AuthStore`, `ScheduleStore`, `AvailabilityStore`, `TimeStore`, `PayStore`,
  `AssistantStore`), provided through a root store and a React context.
- Stores own server state and async actions; **components observe stores and never call `fetch`**.
- All HTTP goes through the typed API client in `client/src/api/`, which attaches the JWT and turns the error shape
  into a typed `ApiError`.
- Derived values are MobX `computed`, not recalculated in components.
- The client never computes pay or validates scheduling rules as the source of truth; it shows what the server
  returns.

## Screens

- **Employee screens are mobile-first** (design at 375 px wide, then widen). **Manager screens are desktop-first**
  but must remain usable on a tablet.
- Every screen that loads data has explicit **loading**, **empty** and **error** states.
- Role-based routes (`/manager/*`, `/me/*`) hide what a role can't use; the server remains the real guard.
- Destructive or publishing actions (publish schedule, delete entry) ask for confirmation.
- Assistant proposals render **Confirm / Cancel**; Confirm calls the normal REST endpoint through the store.

## Components

- Mantine components and theme before custom CSS. No inline styles except one-off layout tweaks.
- Components are small and typed; props interfaces are named `<Component>Props`.
- Times are displayed in `Asia/Jerusalem`; money with two decimals and the currency symbol (₪).
- Accessibility: every input has a label, every icon button has an `aria-label`, color is never the only signal
  (e.g. availability status shows text or an icon too).
