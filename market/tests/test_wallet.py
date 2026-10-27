from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from market.exceptions import BusinessError
from market.models import Campaign, Order, Reservation, User, WalletTransaction
from market.services import cancel_reservation, reserve, settle_campaign, top_up_wallet
from market.tests.test_market import fixtures


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], FAKE_WALLET_ENABLED=True
)
class WalletTests(TestCase):
    def setUp(self):
        self.seller, self.buyer, self.product, self.campaign = fixtures()
        User.objects.filter(pk=self.buyer.pk).update(wallet_balance=0)
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def balance(self):
        self.buyer.refresh_from_db()
        return self.buyer.wallet_balance

    def fund(self, amount=500_000):
        top_up_wallet(self.buyer, amount, uuid4())

    def expire(self):
        Campaign.objects.filter(pk=self.campaign.pk).update(
            deadline=timezone.now() - timedelta(seconds=1)
        )

    def test_top_up_is_idempotent_and_history_private(self):
        reference = str(uuid4())
        payload = {"amount": 500_000, "reference": reference}
        for _ in range(2):
            response = self.client.post("/api/wallet/", payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["balance"], 500_000)
        self.assertEqual(WalletTransaction.objects.count(), 1)
        self.assertEqual(
            self.client.post("/api/wallet/", {**payload, "amount": 600_000}).status_code, 400
        )
        other = User.objects.create_user("other")
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get("/api/wallet/").data["transactions"], [])
        self.assertEqual(self.client.post("/api/wallet/", payload).status_code, 400)

    def test_invalid_top_ups_roles_and_environment(self):
        for amount in (0, -100, 9999, 10_000_001, "bad", 10000.5):
            response = self.client.post(
                "/api/wallet/", {"amount": amount, "reference": str(uuid4())}
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.balance(), 0)
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.get("/api/wallet/").status_code, 400)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/wallet/").status_code, 403)
        with override_settings(FAKE_WALLET_ENABLED=False), self.assertRaises(BusinessError):
            self.fund()

    def test_insufficient_balance_rolls_back_reservation_and_capacity(self):
        with self.assertRaises(BusinessError):
            reserve(self.campaign.pk, self.buyer, 1)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.reserved_quantity, 0)
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(WalletTransaction.objects.exists())

    def test_increment_cancel_and_rereserve_refund_only_once(self):
        self.fund()
        reservation = reserve(self.campaign.pk, self.buyer, 1)
        reserve(self.campaign.pk, self.buyer, 2)
        self.assertEqual(self.balance(), 290_000)
        cancel_reservation(reservation.pk, self.buyer)
        self.assertEqual(self.balance(), 500_000)
        with self.assertRaises(BusinessError):
            cancel_reservation(reservation.pk, self.buyer)
        self.assertEqual(self.balance(), 500_000)
        reserve(self.campaign.pk, self.buyer, 1)
        self.expire()
        self.assertTrue(settle_campaign(self.campaign.pk))
        self.assertFalse(settle_campaign(self.campaign.pk))
        self.assertEqual(self.balance(), 500_000)
        self.assertEqual(WalletTransaction.objects.filter(kind="refund").count(), 2)
        self.assertFalse(Order.objects.exists())

    def test_failed_increment_preserves_previous_payment(self):
        self.fund(100_000)
        reservation = reserve(self.campaign.pk, self.buyer, 1)
        with self.assertRaises(BusinessError):
            reserve(self.campaign.pk, self.buyer, 1)
        reservation.refresh_from_db()
        self.campaign.refresh_from_db()
        self.assertEqual((reservation.quantity, reservation.paid_amount), (1, 70_000))
        self.assertEqual(self.campaign.reserved_quantity, 1)
        self.assertEqual(self.balance(), 30_000)
        self.assertEqual(WalletTransaction.objects.filter(kind="payment").count(), 1)

    def test_success_preserves_price_without_charging_twice(self):
        self.fund()
        reserve(self.campaign.pk, self.buyer, 3)
        Campaign.objects.filter(pk=self.campaign.pk).update(group_price=90_000)
        self.expire()
        settle_campaign(self.campaign.pk)
        settle_campaign(self.campaign.pk)
        order = Order.objects.get()
        self.assertEqual((order.unit_price, order.quantity), (70_000, 3))
        self.assertEqual(self.balance(), 290_000)
        self.assertEqual(WalletTransaction.objects.filter(kind="payment").count(), 1)
        self.assertFalse(WalletTransaction.objects.filter(kind="refund").exists())

    def test_legacy_unpaid_reservation_does_not_generate_free_refund(self):
        Reservation.objects.create(
            campaign=self.campaign, buyer=self.buyer, quantity=1, unit_price=70_000
        )
        Campaign.objects.filter(pk=self.campaign.pk).update(reserved_quantity=1)
        self.expire()
        settle_campaign(self.campaign.pk)
        self.assertEqual(self.balance(), 0)
        self.assertFalse(WalletTransaction.objects.exists())

    def test_top_up_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        payload = {"amount": 100_000, "reference": str(uuid4())}
        self.assertEqual(client.post("/api/wallet/", payload).status_code, 403)
        token = client.get("/api/auth/session/").data["csrf_token"]
        self.assertEqual(
            client.post("/api/wallet/", payload, HTTP_X_CSRFTOKEN=token).status_code, 200
        )


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], FAKE_WALLET_ENABLED=True
)
class WalletConcurrencyTests(TransactionTestCase):
    def test_concurrent_top_up_retries_credit_only_once(self):
        buyer = User.objects.create_user("buyer")
        reference = uuid4()
        barrier = Barrier(2)

        def top_up(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return top_up_wallet(buyer, 100_000, reference).pk
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(top_up, range(2)))
        self.assertEqual(results[0], results[1])
        buyer.refresh_from_db()
        self.assertEqual(buyer.wallet_balance, 100_000)
        self.assertEqual(WalletTransaction.objects.count(), 1)

    def test_competing_purchases_cannot_spend_the_same_balance(self):
        seller, buyer, product, campaign = fixtures()
        User.objects.filter(pk=buyer.pk).update(wallet_balance=70_000)
        other = Campaign.objects.create(
            product=product,
            title="Second",
            group_price=70_000,
            min_quantity=1,
            capacity=1,
            buyer_limit=1,
            deadline=timezone.now() + timedelta(days=1),
            status="active",
        )
        barrier = Barrier(2)

        def purchase(campaign_id):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    reserve(campaign_id, buyer, 1)
                    return "paid"
                except BusinessError:
                    return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(
                list(pool.map(purchase, [campaign.pk, other.pk])), ["paid", "rejected"]
            )
        buyer.refresh_from_db()
        self.assertEqual(buyer.wallet_balance, 0)
        self.assertEqual(Reservation.objects.count(), 1)
