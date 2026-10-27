from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from market.exceptions import BusinessError
from market.models import Campaign, Category, Order, Product, Reservation, User
from market.services import cancel_reservation, publish_campaign, reserve, settle_campaign


def fixtures():
    seller = User.objects.create_user("seller", password="Strong-Test-2026!", role="seller")
    buyer = User.objects.create_user(
        "buyer", password="Strong-Test-2026!", role="buyer", wallet_balance=10_000_000
    )
    category = Category.objects.create(name="خوراکی", slug="food")
    product = Product.objects.create(
        name="قهوه", seller=seller, category=category, retail_price=100000, description="نمونه"
    )
    campaign = Campaign.objects.create(
        product=product,
        title="خرید گروهی قهوه",
        group_price=70000,
        min_quantity=3,
        capacity=5,
        buyer_limit=3,
        deadline=timezone.now() + timedelta(days=1),
        status="active",
    )
    return seller, buyer, product, campaign


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class BusinessTests(TestCase):
    def setUp(self):
        self.seller, self.buyer, self.product, self.campaign = fixtures()

    def test_reserve_threshold_and_cancellation(self):
        reservation = reserve(self.campaign.pk, self.buyer, 3)
        self.campaign.refresh_from_db()
        self.assertEqual((self.campaign.status, self.campaign.reserved_quantity), ("funded", 3))
        cancel_reservation(reservation.pk, self.buyer)
        self.campaign.refresh_from_db()
        self.assertEqual((self.campaign.status, self.campaign.reserved_quantity), ("active", 0))
        reserve(self.campaign.pk, self.buyer, 2)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_cumulative_limit_and_capacity(self):
        reserve(self.campaign.pk, self.buyer, 2)
        with self.assertRaises(BusinessError):
            reserve(self.campaign.pk, self.buyer, 2)
        other = User.objects.create_user("other", wallet_balance=10_000_000)
        reserve(self.campaign.pk, other, 3)
        third = User.objects.create_user("third")
        with self.assertRaises(BusinessError):
            reserve(self.campaign.pk, third, 1)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.reserved_quantity, 5)

    def test_successful_settlement_is_idempotent_and_snapshots_price(self):
        reservation = reserve(self.campaign.pk, self.buyer, 3)
        self.campaign.deadline = timezone.now() - timedelta(seconds=1)
        self.campaign.save(update_fields=["deadline"])
        self.assertTrue(settle_campaign(self.campaign.pk))
        self.assertFalse(settle_campaign(self.campaign.pk))
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual((Order.objects.get().unit_price, Order.objects.get().quantity), (70000, 3))
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "converted")
        with self.assertRaises(BusinessError):
            cancel_reservation(reservation.pk, self.buyer)

    def test_failure_releases_and_produces_no_order(self):
        reservation = reserve(self.campaign.pk, self.buyer, 1)
        self.campaign.deadline = timezone.now() - timedelta(seconds=1)
        self.campaign.save(update_fields=["deadline"])
        call_command("process_deadlines", verbosity=0)
        reservation.refresh_from_db()
        self.campaign.refresh_from_db()
        self.assertEqual((reservation.status, self.campaign.status), ("released", "failed"))
        self.assertFalse(Order.objects.exists())

    def test_deadline_and_roles_and_draft(self):
        with self.assertRaises(BusinessError):
            reserve(self.campaign.pk, self.seller, 1)
        self.campaign.status = "draft"
        self.campaign.save()
        with self.assertRaises(BusinessError):
            reserve(self.campaign.pk, self.buyer, 1)
        publish_campaign(self.campaign.pk, self.seller)
        self.campaign.refresh_from_db()
        self.campaign.deadline = timezone.now() - timedelta(seconds=1)
        self.campaign.save()
        with self.assertRaises(BusinessError):
            reserve(self.campaign.pk, self.buyer, 1)

    def test_database_capacity_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Campaign.objects.filter(pk=self.campaign.pk).update(reserved_quantity=6)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ApiTests(TestCase):
    def setUp(self):
        self.seller, self.buyer, self.product, self.campaign = fixtures()
        self.client = APIClient()

    def test_public_listing_and_hidden_drafts(self):
        response = self.client.get("/api/campaigns/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["progress"], 0)
        self.campaign.status = "draft"
        self.campaign.save()
        self.assertEqual(self.client.get("/api/campaigns/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/campaigns/{self.campaign.pk}/").status_code, 404)

    def test_seller_create_publish_buyer_reserve_cancel(self):
        self.client.force_authenticate(self.seller)
        response = self.client.post(
            "/api/products/",
            {
                "name": "چای",
                "category": self.product.category_id,
                "retail_price": 200000,
                "description": "چای نمونه",
                "visual": "tea",
                "unit": "بسته",
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        response = self.client.post(
            "/api/campaigns/",
            {
                "product_id": response.data["id"],
                "title": "چای گروهی",
                "group_price": 150000,
                "min_quantity": 2,
                "capacity": 4,
                "buyer_limit": 2,
                "deadline": (timezone.now() + timedelta(days=2)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data["id"]
        self.assertEqual(self.client.post(f"/api/campaigns/{pk}/publish/").status_code, 200)
        self.client.force_authenticate(self.buyer)
        response = self.client.post(f"/api/campaigns/{pk}/reserve/", {"quantity": 2})
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/reservations/{response.data['id']}/cancel/"
        self.assertEqual(self.client.post(url).status_code, 200)

    def test_permissions_and_ownership(self):
        url = f"/api/campaigns/{self.campaign.pk}/reserve/"
        self.assertEqual(self.client.post(url, {"quantity": 1}).status_code, 403)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.post("/api/products/", {}).status_code, 400)
        reservation = reserve(self.campaign.pk, self.buyer, 1)
        other = User.objects.create_user("stranger", role="seller")
        self.client.force_authenticate(other)
        self.assertEqual(
            self.client.post(f"/api/reservations/{reservation.pk}/cancel/").status_code, 404
        )
        self.assertEqual(
            self.client.post(f"/api/campaigns/{self.campaign.pk}/publish/").status_code, 404
        )
        self.assertEqual(self.client.get("/api/reservations/").data, [])

    def test_invalid_payloads(self):
        self.client.force_authenticate(self.buyer)
        for quantity in (0, -1, "bad", 4):
            response = self.client.post(
                f"/api/campaigns/{self.campaign.pk}/reserve/", {"quantity": quantity}
            )
            self.assertEqual(response.status_code, 400)
        self.client.force_authenticate(self.seller)
        for price in (0, -1, 10_000_000_001):
            invalid_product = self.client.post(
                "/api/products/",
                {
                    "name": "invalid price",
                    "description": "test",
                    "category": self.product.category_id,
                    "retail_price": price,
                },
            )
            self.assertEqual(invalid_product.status_code, 400)
        response = self.client.post(
            "/api/campaigns/",
            {
                "product_id": self.product.pk,
                "title": "bad",
                "group_price": 120000,
                "min_quantity": 10,
                "capacity": 2,
                "buyer_limit": 3,
                "deadline": (timezone.now() - timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_order_fulfillment_permissions_and_transitions(self):
        reserve(self.campaign.pk, self.buyer, 3)
        Campaign.objects.filter(pk=self.campaign.pk).update(deadline=timezone.now())
        settle_campaign(self.campaign.pk)
        order = Order.objects.get()
        url = f"/api/orders/{order.pk}/status/"
        self.client.force_authenticate(self.buyer)
        self.assertEqual(self.client.post(url, {"status": "shipped"}).status_code, 400)
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.post(url, {"status": "completed"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"status": "shipped"}).status_code, 200)
        self.assertEqual(self.client.post(url, {"status": "completed"}).status_code, 200)
        self.assertEqual(self.client.post(url, {"status": "confirmed"}).status_code, 400)

    def test_real_session_csrf_login_logout(self):
        client = APIClient(enforce_csrf_checks=True)
        credentials = {"username": "buyer", "password": "Strong-Test-2026!"}
        self.assertEqual(client.post("/api/auth/login/", credentials).status_code, 403)
        token = client.get("/api/auth/session/").data["csrf_token"]
        response = client.post("/api/auth/login/", credentials, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        token = response.data["csrf_token"]
        url = f"/api/campaigns/{self.campaign.pk}/reserve/"
        self.assertEqual(client.post(url, {"quantity": 1}).status_code, 403)
        self.assertEqual(client.post(url, {"quantity": 1}, HTTP_X_CSRFTOKEN=token).status_code, 201)
        self.assertEqual(client.post("/api/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_signup_validates_password_and_role(self):
        for payload in [
            {
                "username": "new",
                "display_name": "نام",
                "role": "admin",
                "password": "Strong-Test-2026!",
            },
            {"username": "new", "display_name": "نام", "role": "buyer", "password": "123"},
        ]:
            self.assertEqual(self.client.post("/api/auth/signup/", payload).status_code, 400)
        response = self.client.post(
            "/api/auth/signup/",
            {
                "username": "new",
                "display_name": "خریدار جدید",
                "role": "buyer",
                "password": "Strong-Test-2026!",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.data["user"])

    @override_settings(DEBUG=False)
    def test_demo_forbidden_in_production(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo")

    def test_health_and_filters(self):
        self.assertEqual(self.client.get("/api/health/").data["database"], "sqlite")
        self.assertEqual(self.client.get("/api/campaigns/?category=missing").data["count"], 0)
        self.assertEqual(self.client.get("/api/campaigns/?search=قهوه").data["count"], 1)

    @override_settings(DEBUG=True)
    def test_demo_seed_is_repeatable_and_covers_all_campaign_states(self):
        call_command("seed_demo", verbosity=0)
        models = (User, Category, Product, Campaign, Reservation, Order)
        counts = [model.objects.count() for model in models]
        call_command("seed_demo", verbosity=0)
        self.assertEqual([model.objects.count() for model in models], counts)
        self.assertEqual(
            set(Campaign.objects.values_list("status", flat=True)), set(Campaign.Status.values)
        )
        self.assertEqual(Order.objects.count(), 2)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.seller, self.buyer, self.product, self.campaign = fixtures()

    def test_competing_reservations_do_not_oversell_sqlite(self):
        self.assertEqual(connection.vendor, "sqlite")
        self.assertEqual(connection.settings_dict["OPTIONS"]["transaction_mode"], "IMMEDIATE")
        self.campaign.min_quantity = self.campaign.capacity = self.campaign.buyer_limit = 1
        self.campaign.save()
        other = User.objects.create_user("other", wallet_balance=10_000_000)
        barrier = Barrier(2)

        def compete(buyer_id):
            close_old_connections()
            try:
                buyer = User.objects.get(pk=buyer_id)
                barrier.wait(timeout=10)
                try:
                    reserve(self.campaign.pk, buyer, 1)
                    return "reserved"
                except BusinessError:
                    return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(compete, [self.buyer.pk, other.pk]))
        self.assertCountEqual(results, ["reserved", "rejected"])
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.reserved_quantity, 1)
        self.assertEqual(Reservation.objects.filter(status="active").count(), 1)
