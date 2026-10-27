# Design system

Visual direction: a shadcn-inspired neutral marketplace with white surfaces, zinc
typography, fine borders, compact rounded controls, and restrained shadows. Custom
product illustrations retain their natural colors inside neutral frames. Persian
typography, RTL composition, clear progress bars, and generous whitespace remain.
This is a visual treatment of the existing Vue components; it adds no UI dependency.

## Tokens

Defined centrally in `frontend/app/assets/main.css`.

| Token | Value | Use |
|---|---|---|
| background / card | #ffffff | Page, cards, forms |
| foreground | #18181b | Headings and body copy |
| primary | #18181b | Primary actions and progress |
| primary-hover | #27272a | Hover emphasis |
| primary-foreground | #fafafa | Text on primary controls |
| muted-background | #f4f4f5 | Tab groups, supporting surfaces, skeletons |
| muted-foreground | #52525b | Secondary information |
| border | #e4e4e7 | Cards, inputs, dividers |
| accent | #3f3f46 | Editorial labels |
| ring | #71717a | Keyboard focus outline |
| destructive | #b91c1c | Errors and destructive confirmation |
| success / success-background | #166534 / #f0fdf4 | Successful states |

Vazirmatn is bundled locally at weights 400, 500, 600, 700. Base type is 15px;
body copy is generally 13–15px; headings scale up to 54px. Shared spacing rhythm:
4, 8, 12, 16, 20, 24, 32, 40, 64px, adjusted by component density. Container max:
1240px. Card radius: 12px; primary controls: 8px. Tabs use a muted track with a
white selected surface and a small shadow. Buttons and cards change color/border
on hover without bouncing. Keyboard focus uses a 2px zinc outline with an offset.
Low-elevation shadows are used sparingly, with a stronger modal shadow.

## Responsive composition

Breakpoints: 420, 760, 1050, 1440px. Catalog: three columns desktop, two tablet,
one narrow mobile. Hero/detail/auth layouts collapse to one column on mobile.
Mobile navigation uses an explicit expanded button and drawer. Seller tables have
a labelled focusable scroll region; the page itself must not overflow horizontally.

## Interaction and content

- Primary/secondary/compact/danger button variants share sizing and focus behavior.
- Progress shows quantity relative to the minimum; remaining capacity is separate.
- State badges use text plus color. Discounts compare group price with retail price.
- Client quantities have disabled bounds; server enforces cumulative limits.
- Loading skeletons, empty-state guidance, retryable API errors, status notifications.
- Destructive cancellation uses a native dialog (focus trapping and Escape dismissal).
- Animations are short and subtle and disabled under prefers-reduced-motion.
- RTL logical spacing, native Persian copy, `Intl` numbers and Tehran/Persian dates.
- Latin usernames/passwords and numeric/date inputs use LTR direction.

WCAG AA is a design target, verified to the extent recorded in TESTING.md. Automated
accessibility checks cannot prove full screen-reader usability or comprehensive WCAG compliance.
