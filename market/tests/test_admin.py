from datetime import timedelta

from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from market.admin import CampaignAdminForm
from market.models import Campaign, Category, Order, Reservation, User
from market.services import reserve, settle_campaign
from market.tests.test_market import fixtures


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AdminTests(TestCase):
    def setUp(self):
        self.seller, self.buyer, self.product, self.campaign = fixtures()
        self.admin = User.objects.create_superuser("admin", password="Strong-Test-2026!")

    def action(self, model, action, obj):
        return self.client.post(
            reverse(f"admin:market_{model}_changelist"),
            {"action": action, "_selected_action": [obj.pk]},
            follow=True,
        )

    def test_login_requires_staff_and_csrf(self):
        url = reverse("admin:index")
        self.assertRedirects(self.client.get(url), reverse("admin:login") + "?next=" + url)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(url).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        login = reverse("admin:login")
        credentials = {"username": "admin", "password": "Strong-Test-2026!", "next": url}
        self.assertEqual(client.post(login, credentials).status_code, 403)
        self.assertEqual(client.get(login).status_code, 200)
        credentials["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
        self.assertRedirects(client.post(login, credentials), url)

    def test_all_models_and_forms_render(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        for model in ("user", "category", "product", "campaign", "reservation", "order"):
            with self.subTest(model=model):
                self.assertEqual(
                    self.client.get(reverse(f"admin:market_{model}_changelist")).status_code, 200
                )
        for model in ("user", "category", "product", "campaign"):
            self.assertEqual(self.client.get(reverse(f"admin:market_{model}_add")).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("admin:market_campaign_change", args=[self.campaign.pk])
            ).status_code,
            200,
        )

    def test_category_creation_and_custom_user_password(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin:market_category_add"), {"name": "Tea", "slug": "tea", "_save": "Save"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Category.objects.filter(slug="tea").exists())
        response = self.client.post(
            reverse("admin:market_user_add"),
            {
                "username": "managed",
                "display_name": "Managed seller",
                "role": "seller",
                "password1": "Strong-Test-2026!",
                "password2": "Strong-Test-2026!",
                "usable_password": "true",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="managed")
        self.assertEqual((user.role, user.display_name), ("seller", "Managed seller"))
        self.assertTrue(user.check_password("Strong-Test-2026!"))

    def test_staff_needs_model_permissions(self):
        self.buyer.is_staff = True
        self.buyer.save()
        self.client.force_login(self.buyer)
        url = reverse("admin:market_campaign_changelist")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.buyer.user_permissions.add(Permission.objects.get(codename="view_campaign"))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.action("campaign", "settle", self.campaign)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, "active")
        self.assertEqual(
            self.client.post(reverse("admin:market_category_add"), {}).status_code, 403
        )

    def test_reservation_cancellation_preserves_capacity(self):
        reservation = reserve(self.campaign.pk, self.buyer, 3)
        self.client.force_login(self.admin)
        self.action("reservation", "cancel", reservation)
        reservation.refresh_from_db()
        self.campaign.refresh_from_db()
        self.assertEqual(reservation.status, "cancelled")
        self.assertEqual((self.campaign.status, self.campaign.reserved_quantity), ("active", 0))
        response = self.action("reservation", "cancel", reservation)
        self.assertContains(response, "error")
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.reserved_quantity, 0)

    def test_campaign_and_order_actions(self):
        self.client.force_login(self.admin)
        self.campaign.status = "draft"
        self.campaign.save()
        self.action("campaign", "publish", self.campaign)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, "active")
        reserve(self.campaign.pk, self.buyer, 3)
        Campaign.objects.filter(pk=self.campaign.pk).update(deadline=timezone.now())
        self.action("campaign", "settle", self.campaign)
        self.action("campaign", "settle", self.campaign)
        order = Order.objects.get()
        self.action("order", "complete", order)
        order.refresh_from_db()
        self.assertEqual(order.status, "confirmed")
        self.action("order", "ship", order)
        self.action("order", "complete", order)
        order.refresh_from_db()
        self.assertEqual(order.status, "completed")

    def test_published_campaign_fields_are_protected(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("admin:market_campaign_change", args=[self.campaign.pk]),
            {"group_price": 1, "reserved_quantity": 5, "status": "successful", "_save": "Save"},
        )
        self.campaign.refresh_from_db()
        self.assertEqual(
            (self.campaign.group_price, self.campaign.reserved_quantity, self.campaign.status),
            (70000, 0, "active"),
        )

    def test_draft_form_validates_price_deadline_and_capacity(self):
        data = {
            "product": self.product.pk,
            "title": "New campaign",
            "group_price": 70000,
            "min_quantity": 3,
            "capacity": 5,
            "buyer_limit": 3,
            "deadline": timezone.now() + timedelta(days=1),
            "status": "draft",
            "reserved_quantity": 0,
        }
        self.assertTrue(CampaignAdminForm(data=data).is_valid())
        for field, value in (
            ("group_price", 100000),
            ("deadline", timezone.now() - timedelta(days=1)),
            ("capacity", 1),
        ):
            with self.subTest(field=field):
                self.assertFalse(CampaignAdminForm(data={**data, field: value}).is_valid())

    def test_transaction_fields_cannot_be_changed_or_deleted(self):
        reservation = reserve(self.campaign.pk, self.buyer, 3)
        self.client.force_login(self.admin)
        url = reverse("admin:market_reservation_change", args=[reservation.pk])
        self.client.post(url, {"quantity": 100, "status": "cancelled", "_save": "Save"})
        reservation.refresh_from_db()
        self.assertEqual((reservation.quantity, reservation.status), (3, "active"))
        self.assertEqual(
            self.client.post(
                reverse("admin:market_reservation_delete", args=[reservation.pk])
            ).status_code,
            403,
        )
        for model in ("reservation", "order"):
            self.assertEqual(self.client.get(reverse(f"admin:market_{model}_add")).status_code, 403)
        Campaign.objects.filter(pk=self.campaign.pk).update(
            deadline=timezone.now() - timedelta(seconds=1)
        )
        settle_campaign(self.campaign.pk)
        order = Order.objects.get()
        self.assertEqual(
            self.client.get(reverse("admin:market_order_change", args=[order.pk])).status_code, 200
        )
        self.assertEqual(Reservation.objects.count(), 1)
