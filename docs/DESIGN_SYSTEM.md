# Design system

Visual direction: a calm, editorial marketplace for thoughtful local purchasing.
Warm paper, deep botanical green, restrained copper accents, custom packaging
illustrations, clear progress bars, generous whitespace. No external image dependency.

## Tokens

Defined centrally in `frontend/app/assets/main.css`.

| Token | Value | Use |
|---|---|---|
| ink | #203c34 | Headings and structural emphasis |
| text | #354b43 | Body copy |
| muted | #5d6b62 | Secondary information |
| green | #255846 | Primary actions and progress |
| green-dark | #193e32 | Hover/active emphasis |
| green-soft | #eaf1e9 | Supporting surfaces |
| cream | #f8f8f2 | Page background |
| paper | #ffffff | Cards and forms |
| line | #dce2d9 | Boundaries |
| accent | #97552f | Editorial highlights |
| danger | #a13232 | Destructive confirmation |

Vazirmatn is bundled locally at weights 400, 500, 600, 700. Base type is 15px;
body copy is generally 13–15px; headings scale up to 54px. Shared spacing rhythm:
4, 8, 12, 16, 20, 24, 32, 40, 64px, adjusted by component density. Container max:
1240px. Card radius: 18px; controls: 9–10px. One low-elevation card shadow is used
sparingly, with a stronger modal shadow.

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
