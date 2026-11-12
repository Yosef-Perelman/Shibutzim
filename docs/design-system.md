# Shibutzim – Design system

The visual rules of the client. They are **derived** from four reference screenshots of a workforce-management
product (kept locally in `design/references/`, never committed) and corrected where the reference fails
accessibility. The Mantine theme (`client/src/theme.ts`) implements this document; the style preview at `/design`
shows every token and state below. When this file and the theme disagree, fix the theme.

## 1. Character

Calm, light and friendly: an off-white page, soft beige cards without borders, one deep navy for text and strong
surfaces, one sky blue for actions. Large rounded shapes, pill buttons, generous whitespace, almost no shadow. The
product is used by people between tasks on a phone, so every screen answers one question and has one obvious action.

What we take from the references:

- Beige cards on an off-white page instead of white cards with borders.
- Navy as the text color and as the fill of icon tiles and the selected state of a segmented control.
- Pill-shaped buttons, a filled primary and an outlined secondary of the same height.
- A flat white header with a very soft shadow below it.
- Tabs as plain text with a navy underline on the active one.
- Large, quiet headings and muted grey body text.

What we change on purpose:

- The references use white text on light sky blue (contrast 2.99:1, below the 4.5:1 minimum). Filled buttons use a
  deeper blue (§2.2); the sky blue stays for icons, focus rings and large decoration.
- The references use a light grey body text (3.5:1 on their cards). Muted text uses a darker grey (§2.1).
- The references are Hebrew and right-to-left. The client is **English, left to right** (plan 003, open question 8).
  Layout code uses logical properties (`margin-inline-start`, `padding-inline`), never `left` / `right`, so a
  right-to-left language can be added later without redoing the layout.

## 2. Color

All text and control colors below meet WCAG AA (4.5:1 for text, 3:1 for large text and component edges) on the
surface named next to them. Ratios were computed, not estimated.

### 2.1 Neutrals

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `page` | `#fbfaf9` | page background | – |
| `surface` | `#ffffff` | header, dialogs, inputs, menus | – |
| `card` | `#f2eeea` | cards and panels on the page; no border | – |
| `card-strong` | `#ebe7e2` | hover on a card, table header, neutral badge fill | – |
| `line` | `#e3ded8` | dividers, input border, table row line | – |
| `ink` | `#1f1c42` | body text, headings, icon tiles, selected pill | 15.5:1 on `page`, 14.0:1 on `card` |
| `ink-muted` | `#6b677a` | secondary text, captions, placeholders, labels of metadata | 5.2:1 on `page`, 4.7:1 on `card` |
| `ink-disabled` | `#a3a1af` | disabled controls only, never information | 2.4:1 (exempt: disabled) |

### 2.2 Brand and action

| Token | Hex | Use | Contrast |
|---|---|---|---|
| `primary` | `#2f6fe0` | filled primary button, links, active tab text, focus fill | white on it 4.7:1 |
| `primary-hover` | `#2b62c9` | hover and pressed state of the primary button | white on it 5.7:1 |
| `primary-text` | `#245bc4` | link text on tinted backgrounds | 6.2:1 on white |
| `primary-tint` | `#e4eefd` | selected row, info badge fill, hover of the outline button | `ink` on it 13.8:1 |
| `sky` | `#4d96f8` | the reference's brand blue: icons, focus ring, illustrations, large decoration; **never behind small text** | – |

### 2.3 Status

Every status has a text color, a tint fill and an icon. **Color is never the only signal** (ui-rules): a badge
always carries its word and icon.

| Meaning | Text | Fill | Icon (Tabler) | Contrast |
|---|---|---|---|---|
| success | `#166c3b` | `#e3f4ea` | `IconCheck` | 5.7:1 |
| warning | `#8a5a00` | `#fdf0d5` | `IconAlertTriangle` | 5.3:1 |
| danger | `#b42318` | `#fde8e6` | `IconAlertCircle` | 5.6:1 |
| info | `#2155b8` | `#e4eefd` | `IconInfoCircle` | 5.9:1 |
| neutral | `#5f5b70` | `#ebe7e2` | – | 5.3:1 |

Domain statuses use those colors, so the same word always looks the same:

| Domain value | Label | Color | Icon |
|---|---|---|---|
| availability `available` | Available | success | `IconCheck` |
| availability `preferred` | Preferred | purple: text `#5b3fc4` on `#ece8fb` (5.9:1) | `IconStar` |
| availability `unavailable` | Unavailable | neutral | `IconX` |
| schedule `draft` | Draft | warning | `IconPencil` |
| schedule `published` | Published | success | `IconCircleCheck` |
| no schedule yet | No schedule | neutral | `IconCalendarOff` |
| coverage complete (`assigned == required`) | e.g. 3 / 3 | success | `IconCheck` |
| coverage short | e.g. 2 / 3 | danger | `IconAlertCircle` |
| edit warning from the server | the server's `message` | warning | `IconAlertTriangle` |
| blocking error from the server | the server's `message` | danger | `IconAlertCircle` |

Purple is used for `preferred` only; it is the one color not taken from the references, added so `preferred` is
distinguishable from `available` without relying on the icon alone.

## 3. Typography

- **Font stack:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`. No
  web font in v1 (it would be a new dependency; see plan 003). Numbers use `font-variant-numeric: tabular-nums` in
  tables and pay so columns line up.
- Headings are regular to medium weight in `ink`, never bold-black; emphasis comes from size and whitespace, as in
  the references. Buttons and tabs are medium (500), labels medium, body regular (400).

| Role | Size / line height | Weight | Where |
|---|---|---|---|
| `display` | 40 / 48 | 400 | manager screen title on desktop only |
| `h1` | 28 / 36 | 500 | screen title (mobile: 24 / 32) |
| `h2` | 22 / 30 | 500 | card or section title |
| `h3` | 18 / 26 | 500 | list group title, dialog title |
| `body` | 16 / 24 | 400 | default text, form values |
| `body-sm` | 14 / 20 | 400 | secondary text, table cells on desktop |
| `caption` | 12 / 16 | 500 | badges, helper text, timestamps |

Body text on phones is never below 16 px (it also stops iOS from zooming on input focus). Line length stays under
about 70 characters.

## 4. Spacing, radius, elevation, layout

**Spacing** uses a 4 px base. Tokens: `xs 4`, `sm 8`, `md 16`, `lg 24`, `xl 32`, `2xl 48`, `3xl 64`.
Space inside a card is `lg` (16 on phones); between cards `md`; between page sections `xl`.

**Radius** is large and consistent:

| Token | px | Use |
|---|---|---|
| `radius-sm` | 8 | inputs, small badges' inner shapes |
| `radius-md` | 12 | icon tiles, menus, notifications |
| `radius-lg` | 24 | cards, panels, dialogs, shift cards |
| `radius-pill` | 999 | buttons, segmented controls, badges, tabs' selected pill |

**Elevation** is almost flat. Cards have **no shadow and no border**, only the beige fill. Two shadows exist:

- `shadow-header`: `0 2px 8px rgba(31, 28, 66, 0.08)` for the sticky header and the mobile bottom bar.
- `shadow-overlay`: `0 12px 32px rgba(31, 28, 66, 0.16)` for dialogs, menus and notifications.

**Layout**

- Employee screens are designed at **375 px** (checked in a real 375 px frame, not a resized window) and widened: one column, content width up to 640 px, centered.
  The primary action is reachable by thumb (bottom of the screen or in the card), touch targets are at least
  **44 × 44 px**, the navigation is a bottom bar of four items (Shifts, Availability, Pay, Assistant).
- Manager screens are **desktop-first** (design at 1280 px, content width up to 1200 px) and stay usable at 768 px
  (the week grid scrolls horizontally inside its own container; the page never does). The navigation is a top bar of five items (Schedule, Team, Team pay, My pay, Assistant).
- A screen has one title (`h1`), at most one primary button, and the same three states everywhere (§6.5).
- Page padding is 16 px on phones, 24 px on tablets and 32 px on desktops. Never less than 16 px at the sides.

## 5. Mantine mapping

| Design token | Mantine |
|---|---|
| `primary`, `primary-hover` | `theme.colors.shibutzim` (10-step scale with `#2f6fe0` as shade 6, `#2b62c9` as shade 7), `primaryColor: 'shibutzim'`, `primaryShade: 6` |
| `ink`, `card`, `page`, `line` | `theme.colors.ink` and `theme.colors.sand` scales; `body` background `page`; `Card` / `Paper` default `card` fill |
| status colors | `theme.colors.success`, `warning`, `danger`, `purple` scales; `Badge` variant `light` with the table in §2.3 |
| radius | `theme.radius` (`sm 8`, `md 12`, `lg 24`, `xl 999`), `defaultRadius: 'lg'` for cards, components override to `xl` |
| spacing | `theme.spacing` with the values of §4 |
| type scale | `theme.fontSizes`, `theme.headings` |
| shadows | `theme.shadows.sm` = `shadow-header`, `theme.shadows.xl` = `shadow-overlay` |
| focus ring | `theme.focusRing: 'always'`; 2 px `sky` outline with 2 px offset |

Mantine components and the theme come first; custom CSS only for the layout of a screen (ui-rules).

## 6. Components

### 6.1 Buttons

| Variant | Look | Use |
|---|---|---|
| Primary | filled `primary`, white text, pill, height 44 | the one main action of a screen or dialog |
| Secondary | outline: 1.5 px `primary` border, `primary` text, transparent fill, same shape | alternative actions beside a primary |
| Subtle | text only, `primary` color, `primary-tint` on hover | tertiary actions, "Retry", "Cancel" |
| Danger | filled `danger`, white text | confirmed destructive actions only (remove assignment) |
| Icon button | 44 × 44 hit area, `aria-label` always | toolbar and card actions |

Do: one primary per screen; put the primary on the right of a button pair on desktop and on top on phones; show a
loading state in the button while a request runs; disable it with `ink-disabled` only when the reason is visible.
Don't: two primaries side by side; sky blue behind button text; icon-only buttons without a label; buttons that
shrink below 44 px on phones.

### 6.2 Inputs and forms

- White fill, 1 px `line` border, `radius-sm`, height 44 on phones, label **above** the field in `body-sm`
  medium, helper text in `caption` `ink-muted`, error text in `danger` with `IconAlertCircle` below the field.
- Focus: 2 px `sky` ring. Invalid: `danger` border plus the error text.
- Do: a visible label for every input; show the server's `error.message` next to the control that caused it.
  Don't: placeholder as the only label; red border without text.
- **Three-state availability control:** three equal tiles (Available, Preferred, Unavailable), the icon above the
  word, so all three words fit on a 375 px screen. The selected tile is filled with the status text color
  (`#166c3b`, `#5b3fc4`, `#6b677a`) and white text (6.5:1, 7.1:1, 5.5:1), so the selection is visible by fill, icon
  and word. Unselected tiles are `surface` with `ink` text. `radius-lg`, not a pill, because the tiles are taller.

### 6.3 Cards, lists and tables

- **Card:** `card` fill, `radius-lg`, padding `lg`, no border, no shadow. Title `h2` or `h3`, content `body`.
  A clickable card gets `card-strong` on hover and a visible focus ring.
- **Icon tile:** 44 × 44 (card header) or 32 × 32 (inline), `ink` fill, white icon, `radius-md`. Use for the type
  of a card (shift, pay, warning), as in the references.
- **Shift card (manager board):** `card` fill; name and local time on the first line, coverage badge top right,
  assigned names as a list below, actions in a trailing menu. Today's column has a `primary-tint` header.
- **Employee shift row:** the employee's own assignments sit first on a `primary-tint` card with an `IconUser`
  and the word "You"; the rest of the team follows on plain `card`s.
- **Table:** header row `card-strong` with `body-sm` medium `ink`, rows separated by `line`, numbers right-aligned
  and tabular, totals row in medium weight. On phones a table becomes a list of cards; no horizontal scroll on
  employee screens.
- Do: money as `₪` plus two decimals (`₪412.50`), hours as the server's display hours, times in `Asia/Jerusalem`
  in 24-hour format (`07:00–15:00`), dates like `Sun 15 Nov`. Don't: compute or round values in the client.

### 6.4 Badges, tabs, navigation

- **Badge:** pill, `caption`, status text color on status fill, icon plus word. Never a colored dot alone.
- **Tabs:** plain text, `ink-muted` when inactive, `ink` with a 2 px `ink` underline when active, a `line` under the
  whole row; used for the week range and the pay month.
- **Header:** `surface`, 56 px high on phones and 64 on desktops, `shadow-header`; the brand mark on the start side,
  the current user's name with a role badge and the user menu on the end side.
- **Bottom bar (employee, phones):** `surface`, `shadow-header` flipped upward, four items with icon and label,
  active item in `primary` text with the filled icon.

### 6.5 States every data screen has

| State | Look |
|---|---|
| Loading | skeletons in the shape of the final content (`card` fill pulsing to `card-strong`, on the page background); no full-page spinner |
| Empty | centered icon tile, `h3` message that says what is missing, one `body` sentence saying why or what to do, and the action if one exists (e.g. "Schedule not published yet") |
| Error | `danger` alert card with `IconAlertCircle`, the server's `error.message`, and an outlined danger **Retry** button; never a blank page and never a raw stack trace or status code alone |

### 6.6 Dialogs and notifications

- **Dialog:** `surface`, `radius-lg`, `shadow-overlay`, `h3` title, content, then buttons: primary on the end side,
  subtle Cancel beside it. Publishing and removing ask for confirmation in a dialog that names the thing
  ("Publish the schedule for 15–21 Nov? Employees will see it immediately.").
- **Notification (toast):** `surface`, `radius-md`, `shadow-overlay`, 4 px start border in the status color plus the
  status icon; success toasts close after 4 s, warnings and errors stay until dismissed.

## 7. Accessibility checklist

- Every input has a visible label; every icon button has an `aria-label`.
- Color is never the only signal: statuses carry an icon and a word; selected states carry shape or an icon.
- Text contrast is at least 4.5:1, large text and component borders at least 3:1 (the tables above).
- Focus is always visible (`sky` ring); the tab order follows the reading order; dialogs trap focus and return it.
- Touch targets are at least 44 × 44 px on phones.
- Motion is limited to short fades and skeleton pulses; it respects `prefers-reduced-motion`.

## 8. Out of scope of v1

Dark mode, a custom web font, right-to-left layout, illustrations and photography (the references use them for
marketing; the app does not), and a component library beyond Mantine.
