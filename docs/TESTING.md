# Testing and verification

This document records executed checks and their scope. Final integration results are
updated after browser testing. No public deployment is part of this delivery.

## Backend

`uv run python manage.py test --noinput`: 16 tests pass against a file-backed SQLite
test database. Tests cover public visibility, search/filtering, seller creation and
publication, buyer reserve/cancel, cumulative limits and capacity, deadlines, success
and failure settlement, one-order idempotence, access control, password/role validation,
real session CSRF enforcement, fulfillment transitions, database constraints, demo
production guard, and a two-thread/two-connection last-slot race.

Test classes use the MD5 password hasher only to avoid slow password hashing in unit
tests. Application and seeded users retain Django's default secure password hasher.
Database `test.sqlite3` is isolated from `db.sqlite3`; do not run test commands concurrently.

Ruff lint and formatting pass. Django system checks and migration drift checks pass.
Demo seeding and one-shot deadline processing have been executed.

## Frontend and integration

ESLint and Nuxt TypeScript checks pass after aligning Vue Router with Nuxt's installed
dependency requirements. Production build and browser results are recorded below when
complete. `tests/marketplace.spec.ts` is the reproducible integration suite.

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

Pending production build and browser suite execution.
