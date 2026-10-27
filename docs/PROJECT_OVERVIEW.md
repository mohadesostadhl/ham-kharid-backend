# Hamkharid — collective purchasing

Small producers need predictable demand; individual buyers want fair prices without
buying wholesale quantities. Hamkharid aggregates reservations into time-limited
campaigns. If demand reaches a published quantity threshold at the deadline, active
reservations become orders at a fixed group price. Otherwise they are released.

The Persian web application supports buyers and sellers. Buyers discover campaigns,
reserve within limits, cancel before the deadline, and follow orders. Sellers create
products, publish campaigns, and record shipment and delivery.

This is an academic MVP with fictional demonstration data and a simulated wallet.
It does not collect real payments, shipping addresses, or real fulfillment commitments.
Real payment and shipping coordination
are explicitly outside the application. Product illustrations are original SVG artwork,
not photographs of actual goods.

## Repository map

- `backend/`: independent Git repository; Django/DRF API, SQLite, migrations, tests,
  management commands, and these shared technical documents.
- `frontend/`: independent Git repository; Nuxt/Vue/TypeScript application and integration tests.
- Parent `.runtime/`: ignored bootstrap downloads and archived initial root Git history.
  No runtime dependency on PostgreSQL remains.

SQLite replaces the initial PostgreSQL requirement at the user's explicit request.
Both repositories remain local; no remote repository or hosted Site is created.

## Presentation path

Read SETUP_GUIDE, BUSINESS_RULES, ARCHITECTURE, and PRESENTATION_GUIDE. Start the API,
frontend, and deadline worker. Seeded campaigns immediately demonstrate active,
funded, successful, failed, and draft states.
