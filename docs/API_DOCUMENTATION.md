# API

Prefix: `/api/`. JSON input/output; trailing slashes required. Access via the Nuxt
origin in the browser. Session cookies and `X-CSRFToken` protect mutations.

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | health/ | Public | Database connectivity; `{status:"ok",database:"sqlite"}` |
| GET | auth/session/ | Public | Current user/null and `csrf_token` |
| POST | auth/signup/ | CSRF | username, password, display_name, role (buyer/seller) |
| POST | auth/login/ | CSRF | username, password; rotates CSRF token |
| POST | auth/logout/ | Auth + CSRF | Ends session, returns fresh CSRF token |
| GET | wallet/ | Buyer | Balance, fake_top_up_enabled, latest 50 transactions |
| POST | wallet/ | Buyer + CSRF | Fake top-up `{amount: integer, reference: UUID}` |
| GET | categories/ | Public | Category array |
| GET, POST | products/ | Seller | Own products / create product |
| GET | campaigns/ | Public | Paginated published campaigns |
| GET | campaigns/{id}/ | Public | Published detail |
| POST | campaigns/ | Seller | Create owned-product draft |
| POST | campaigns/{id}/publish/ | Owner | Publish draft |
| POST | campaigns/{id}/reserve/ | Buyer | Add `{quantity: integer}` units |
| GET | reservations/ | Buyer | Own reservation array |
| GET | reservations/{id}/ | Owner | Own reservation detail |
| POST | reservations/{id}/cancel/ | Owner | Cancel active reservation |
| GET | orders/ | Auth | Buyer-owned or seller-owned orders |
| GET | orders/{id}/ | Owner | Order detail |
| POST | orders/{id}/status/ | Seller owner | `{status:"shipped"}` then `completed` |

Campaign queries: `category=<slug>`, `search=<text>`, `status=<state>`, `page=<n>`.
`mine=1` returns only the signed-in seller's campaigns including drafts. Campaign
responses: `{count,next,previous,results}` with 24 items/page. Other lists are arrays.

## Creation examples

```json
{"name":"قهوهٔ نمونه","description":"دادهٔ ساختگی","category":1,"retail_price":100000,"unit":"بسته","visual":"coffee"}
```

```json
{"product_id":1,"title":"کمپین نمونه","group_price":75000,"min_quantity":10,"capacity":30,"buyer_limit":5,"deadline":"2027-01-01T12:00:00+03:30"}
```

Product visuals: coffee, olive, honey, tea, saffron, ceramic. Campaign responses
embed product data, progress (0–100 toward threshold), reserved_quantity, capacity,
and participant_count. Orders expose campaign_title, campaign_id, buyer_name,
quantity, unit_price, total, status, created_at. No password/hash is serialized.

Wallet top-up amounts range from 10,000 to 10,000,000 toman. Reuse the reference UUID
only when retrying the same payment request; repeated references do not add credit.
Transactions contain id, kind (top_up/payment/refund), signed amount, balance_after,
campaign_title (nullable), and created_at. Balance and history are private to the buyer.
Reservation responses include unit_price (captured at reservation) and paid_amount
(zero after refund, or for historical reservations without wallet payments).

## Errors and security

DRF validation/business errors return `{"errors": ...}` with field maps, arrays, or
a detail string. Input violations use 400. Session/CSRF denial uses 403. Unowned
resources return 404. Malformed login CSRF rejected by Django middleware can return
HTML 403; the frontend provides a generic recovery message for non-JSON failures.
Auth endpoints have a 30/hour/IP scoped throttle; other requests use DRF defaults
configured in settings. Never expose development credentials or DEBUG in production.
