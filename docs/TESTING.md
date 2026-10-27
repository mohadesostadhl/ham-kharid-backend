# Testing and verification

This document records checks executed on 2026-10-27 and their scope.
No public deployment is part of this delivery.

## Backend

`uv run python manage.py test --noinput`: 36 tests pass against a file-backed SQLite
test database. Tests cover public visibility, search/filtering, seller creation and
publication, buyer reserve/cancel, cumulative limits and capacity, deadlines, success
and failure settlement, one-order idempotence, access control, password/role validation,
real session CSRF enforcement, fulfillment transitions, database constraints, demo
production guard, repeatable seeding across every campaign state, and a
two-thread/two-connection last-slot race.

Admin and wallet coverage includes staff/model permissions, CSRF, hashed custom-user
creation, immutable transaction fields, workflow actions, insufficient-funds rollback,
incremental charges, price snapshots, refund idempotence, legacy unpaid reservations,
private history, top-up amount validation and environment guard. Concurrent tests
verify that separate campaigns cannot spend the same wallet balance twice and that
simultaneous retries of one top-up produce one credit.

Test classes use the MD5 password hasher only to avoid slow password hashing in unit
tests. Application and seeded users retain Django's default secure password hasher.
Database `test.sqlite3` is isolated from `db.sqlite3`; do not run test commands concurrently.

Ruff lint and formatting pass. Django system checks and migration drift checks pass.
Demo seeding and one-shot deadline processing have been executed.

## Frontend and integration

ESLint, Prettier, Nuxt TypeScript checks, and the Nuxt production build pass after
aligning Vue Router with Nuxt's installed dependency requirements.
`tests/marketplace.spec.ts` is the reproducible integration suite.

Run with backend and frontend on 8000/3000, seeded demo data, and installed Microsoft
Edge (Playwright channel msedge). Use E2E_BASE_URL to select another frontend origin.
Tests add uniquely named fictional users/products/campaigns and retain them for review.
They do not reset the database. The buyer_demo reservation created by the test is
cancelled. The order lifecycle test advances only its own created campaign's deadline
using Django, then runs the real settlement command.

Screenshots, traces on failure, and HTML reports are generated under frontend's
ignored test-results and playwright-report directories. Tests cover 375, 768, 1024,
and 1440px layouts, page overflow, browser runtime errors, common WCAG rules via axe,
buyer and seller mutations, session persistence, errors/retry, and cancellation dialog.
Automated accessibility results do not prove complete WCAG compliance; manual assistive
technology testing remains outside this verification.

## Dependency audit

The npm audit on 2026-10-27 reports seven high-severity affected dependency nodes,
all tracing to node-forge 1.4.0 via listhen/Nitro/Nuxt. The underlying issue is
[GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv), which lists no
patched version at verification time. The certificate utility is not part of this
application's reservation/authentication logic; development uses loopback HTTP.
This remains an upstream dependency advisory and must be reviewed before public
deployment. No downgrade or forced audit repair is applied merely to hide the finding.

## Final integration record

`npm.cmd run test:e2e`: **8 passed**, run against the production Nuxt Node server
and the Django/SQLite API, using Playwright with installed Microsoft Edge.

| Check | Executed result |
|---|---|
| API connectivity through Nuxt | HTTP 200; reports `database: sqlite` |
| Public discovery | Listing, category filtering, product/title search, empty results pass |
| Buyer workflow | Real login, CSRF-protected reservation, reload persistence, cumulative limit, cancellation dialog, logout pass |
| Seller workflow | New account, product creation, draft campaign, publication pass |
| Campaign and order integration | Buyer reaches threshold; real deadline command creates order; seller records shipment and delivery |
| Signed-in phone screens | Buyer reservations/orders, seller table, product/campaign forms pass overflow checks |
| Responsive routes | Catalog, detail, login, guide, account, seller at 375/768/1024px pass |
| Desktop | 1440px catalog and seller workflow pass |
| Automated accessibility | Zero axe violations in scanned WCAG A/AA rule sets on the tested routes and mobile seller form/dashboard |
| Browser runtime | No uncaught page errors in discovery test |
| Recovery | Simulated API failure displays retry; retry restores catalog |
| Visual review | Desktop catalog/seller and mobile login/detail/seller/form screenshots inspected |

Contrast findings from the first scan were fixed by darkening secondary text and
accent labels. A duplicate login-page heading was corrected. The final suite passes
without skipping tests or suppressing accessibility rules.

Generated artifacts: `frontend/playwright-report/index.html` and
`frontend/test-results/`. These remain ignored by Git. After verification the
integration database is archived at parent `.runtime/verified-integration.sqlite3`,
and the normal development database is freshly migrated and seeded for presentation.
Future E2E runs add their own fictional records to the selected local database.

Both independent repositories finish on `main` with clean working trees and local
feature/test merge commits. Neither has a remote. No source was published or pushed.

## Verification limits

### Wallet and color refresh (2026-10-27)

The nine-test browser suite passed against isolated `backend/wallet-qa.sqlite3`,
Django on port 8005 and Nuxt on 3105. Coverage includes fake top-up, insufficient
funds, successful ordering without a second debit, failed-campaign refund exactly
once, cancellation, private account screens and transaction history. Seller order
fulfillment still passes. Automated accessibility and overflow checks pass at
375/768/1024px and on the desktop wallet. Desktop home/account and mobile account
screenshots were visually inspected. Existing development servers/databases were
not used for these browser tests. The normal development database received only
the new schema/data migrations, preserving its existing records and balances.

### Shadcn-style refresh (2026-10-27)

The neutral theme was rebuilt and the full eight-test browser suite rerun:
**8 passed**. ESLint, Prettier, and Nuxt type checks also pass. Desktop catalog and
seller screenshots plus mobile login, seller dashboard, and campaign forms were
visually reviewed. A shared input selector regression found during screenshot
review was corrected before the final run; no accessibility rules were suppressed.

The final refresh run used the production UI on port 3101, an isolated Django API
on 8001, and a temporary QA routing origin on 3100. Both API requests and deadline
commands used parent `.runtime/shadcn-qa.sqlite3`. Existing user development servers
on 3000/8000 were retained. The application API proxy configuration is unchanged.
Stored credentials for seller_demo, seller_second, buyer_demo, and buyer_demo_2
were verified against the normal local database.

### Scope

The suite verifies the stated local MVP, not real payment, delivery, load endurance,
complete manual screen-reader behavior, or a production deployment. The SQLite
concurrency test proves the tested last-slot race; it is not a throughput benchmark.
Upstream dependency risk remains as documented above. Runtime servers and the worker
are stopped after verification; restart them using SETUP_GUIDE.md.
