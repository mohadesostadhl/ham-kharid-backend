# Requirements and scope

## Functional requirements

| Actor | Requirement | Implementation |
|---|---|---|
| Visitor | Discover, search, filter, inspect campaigns | Public campaign/category API and catalog/detail screens |
| Visitor | Register as buyer or seller and sign in/out | Django session authentication, validated passwords, CSRF |
| Buyer | Reserve positive quantities within remaining capacity and cumulative buyer limit | Transactional `reserve` service |
| Buyer | Cancel an active reservation before the deadline | Cancellation confirmation and transactional service |
| Buyer | View only own reservations and orders | Queryset filtering and account screen |
| Seller | Create own products and draft campaigns | Seller panel, typed forms, serializer ownership checks |
| Seller | Publish valid draft campaigns | Owner-only publish action |
| Seller | View own products, campaigns, orders; advance fulfillment | Seller dashboard and order transitions |
| System | Recalculate threshold state after reservation/cancellation | Campaign quantity counter and service |
| System | Finalize due campaigns without duplicate orders | Deadline command, atomic settlement, one-to-one order |

Published conditions are immutable through the API. Editing/deleting products,
campaigns, reservations, or orders is deliberately not exposed. Cancellation is a
status transition, preserving history. One buyer/campaign reservation row is reused
when a cancelled reservation is reactivated.

## Non-functional requirements

- Native Persian/RTL layout, locally bundled Vazirmatn, Persian numbers and dates.
- Shared semantic design tokens, responsive cards/forms/navigation and scrollable tables.
- Loading, empty, error, success, disabled, and confirmation states.
- Semantic controls, visible keyboard focus, native modal dialog, reduced-motion support.
- Typed API contracts, Vue Composition API, focused service functions and components.
- SQLite immediate transactions serialize writes; database checks enforce capacity invariants.
- Testable business rules and end-to-end integration; Ruff, ESLint, Prettier, TypeScript.
- Reproducible fictional demo data; seed command refuses to run outside DEBUG mode.
- Independent local Git histories, Conventional Commits, feature merges, no publishing.

## Explicit limits

No payments, refunds, inventory synchronization outside campaign capacity, messaging,
email verification, password reset, multi-currency, address management, or background
queue infrastructure. These are future extensions, not implied working features.
This is a local demonstrator. A public production launch needs deployment hardening,
shared throttling storage, recovery/monitoring, and resolution of upstream dependency advisories.
