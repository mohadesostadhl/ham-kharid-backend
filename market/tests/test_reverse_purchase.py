from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from market.models import PurchaseOffer, PurchaseRequest, User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ReversePurchaseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.buyer = User.objects.create_user("buyer", role="buyer")
        self.other = User.objects.create_user("other", role="buyer")
        self.seller = User.objects.create_user("seller", role="seller")
        self.purchase_request = PurchaseRequest.objects.create(
            buyer=self.buyer,
            title="خرید چای",
            description="چای ایرانی",
            quantity=10,
            max_unit_price=100000,
            deadline=timezone.now() + timedelta(days=1),
        )
        self.url = f"/api/purchase-requests/{self.purchase_request.pk}/"

    def offer(self, price=90000):
        self.client.force_authenticate(self.seller)
        return self.client.post(
            self.url + "offer/", {"unit_price": price, "description": "ارسال رایگان"}
        )

    def test_complete_flow_and_public_listing(self):
        offer = self.offer()
        self.assertEqual(offer.status_code, 201)
        self.client.force_authenticate(self.buyer)
        response = self.client.post(self.url + "accept/", {"offer_id": offer.data["id"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "closed")
        self.assertTrue(response.data["offers"][0]["is_accepted"])
        self.client.force_authenticate(None)
        response = self.client.get("/api/purchase-requests/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_only_buyer_can_create_and_owner_is_server_assigned(self):
        data = {
            "title": "درخواست جدید",
            "description": "نمونه",
            "quantity": 2,
            "max_unit_price": 20000,
            "deadline": timezone.now() + timedelta(days=2),
            "buyer": self.other.pk,
            "status": "closed",
        }
        self.client.force_authenticate(self.seller)
        self.assertEqual(self.client.post("/api/purchase-requests/", data).status_code, 400)
        self.client.force_authenticate(self.buyer)
        response = self.client.post("/api/purchase-requests/", data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["buyer"], self.buyer.pk)
        self.assertEqual(response.data["status"], "open")

    def test_invalid_request_values_and_guest_write(self):
        self.assertEqual(self.client.post("/api/purchase-requests/", {}).status_code, 403)
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            "/api/purchase-requests/",
            {
                "title": "نمونه",
                "description": "نمونه",
                "quantity": 0,
                "max_unit_price": 0,
                "deadline": timezone.now() - timedelta(days=1),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data["errors"]), {"quantity", "max_unit_price", "deadline"})

    def test_offer_price_roles_and_duplicates(self):
        self.assertEqual(self.offer(100001).status_code, 400)
        self.assertEqual(self.offer(0).status_code, 400)
        self.assertEqual(self.offer().status_code, 201)
        self.assertEqual(self.offer().status_code, 400)
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            self.url + "offer/",
            {
                "unit_price": 50000,
                "description": "نمونه",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PurchaseOffer.objects.count(), 1)

    def test_only_owner_can_accept_and_cannot_select_twice(self):
        offer = self.offer().data
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.post(self.url + "accept/", {"offer_id": offer["id"]}).status_code, 400
        )
        self.client.force_authenticate(self.buyer)
        self.assertEqual(
            self.client.post(self.url + "accept/", {"offer_id": offer["id"]}).status_code, 200
        )
        self.assertEqual(
            self.client.post(self.url + "accept/", {"offer_id": offer["id"]}).status_code, 400
        )
        self.assertEqual(self.offer().status_code, 400)

    def test_expired_request_rejects_offer_and_selection(self):
        offer = self.offer().data
        self.purchase_request.deadline = timezone.now() - timedelta(seconds=1)
        self.purchase_request.save()
        self.assertEqual(self.offer().status_code, 400)
        self.client.force_authenticate(self.buyer)
        self.assertEqual(
            self.client.post(self.url + "accept/", {"offer_id": offer["id"]}).status_code, 400
        )

    def test_cannot_accept_offer_from_another_request(self):
        offer = self.offer().data
        other_request = PurchaseRequest.objects.create(
            buyer=self.buyer,
            title="درخواست دوم",
            description="نمونه",
            quantity=1,
            max_unit_price=100000,
            deadline=timezone.now() + timedelta(days=1),
        )
        self.client.force_authenticate(self.buyer)
        response = self.client.post(
            f"/api/purchase-requests/{other_request.pk}/accept/", {"offer_id": offer["id"]}
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PurchaseOffer.objects.get().is_accepted)
