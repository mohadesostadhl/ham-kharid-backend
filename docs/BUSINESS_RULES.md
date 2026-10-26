# Business rules

## Campaign lifecycle

```mermaid
stateDiagram-v2
  [*] --> draft : seller creates
  draft --> active : owner publishes before deadline
  active --> funded : reservations reach minimum
  funded --> active : cancellation drops below minimum
  active --> failed : deadline processed below minimum
  funded --> successful : deadline processed at or above minimum
  successful --> [*]
  failed --> [*]
```

Reaching the minimum does not immediately create orders. Reservations remain
cancellable until the deadline. Funded campaigns accept more reservations up to
capacity. The deadline comparison uses server time; at exact deadline, reservation
and cancellation are closed. A delayed worker never extends that deadline.

Every reservation request adds units. The cumulative active quantity for that buyer
must remain within buyer_limit. There is one reservation row per buyer/campaign.
Cancelled rows can be reactivated before deadline, starting again at zero active units.
Sellers cannot reserve. Only the buyer can cancel their own reservation.

## Reservation and order lifecycle

```mermaid
stateDiagram-v2
  [*] --> active : buyer reserves
  active --> cancelled : buyer cancels before deadline
  cancelled --> active : buyer reserves again
  active --> converted : successful settlement creates order
  active --> released : failed settlement
  converted --> confirmed : order snapshot
  confirmed --> shipped : owner records shipment
  shipped --> completed : owner records delivery
```

Settlement is atomic and idempotent. An order snapshots unit price and quantity;
total is their product. No money is charged. Cancellation after deadline or after
settlement is rejected. Shipping/delivery records must follow the stated order;
buyers and unrelated sellers cannot change fulfillment status.

Drafts are absent from public listings and detail endpoints. Sellers access their
drafts through `mine=1`. Conditions cannot be edited after creation in this MVP.
Publication revalidates ownership, draft status, and future deadline.

## Demo scenarios

The seed dataset supplies coffee below threshold, olive oil near threshold, honey
at threshold, successful saffron with orders, unsuccessful ceramic with released
reservations, a draft, and a one-slot campaign. All identities are fictional.
Buyer-limit and concurrent-capacity rejection are exercised in automated tests.
