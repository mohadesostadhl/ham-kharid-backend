import os
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from market.models import Campaign, Category, Product, User
from market.services import reserve, settle_campaign, top_up_wallet


class Command(BaseCommand):
    help = "Create fictional, development-only sample data. Safe to repeat."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo accounts are forbidden when DEBUG=False.")
        password = os.environ.get("DEMO_PASSWORD", "Demo-Only-2026!")
        sellers = []
        for username, name in [
            ("seller_demo", "کارگاه نمونهٔ سبزینه"),
            ("seller_second", "تولیدی نمونهٔ آوند"),
        ]:
            seller, created = User.objects.get_or_create(
                username=username,
                defaults={"role": "seller", "display_name": name},
            )
            if created:
                seller.set_password(password)
                seller.save()
            sellers.append(seller)
        buyers = []
        for i in range(1, 9):
            buyer, created = User.objects.get_or_create(
                username="buyer_demo" if i == 1 else f"buyer_demo_{i}",
                defaults={"role": "buyer", "display_name": f"خریدار نمونه {i}"},
            )
            if created:
                buyer.set_password(password)
                buyer.save()
                top_up_wallet(buyer, 10_000_000, uuid4())
            buyers.append(buyer)
        categories = [
            Category.objects.get_or_create(slug=slug, defaults={"name": name})[0]
            for slug, name in [
                ("pantry", "خوراکی و نوشیدنی"),
                ("home", "خانه و زندگی"),
                ("natural", "محصولات طبیعی"),
            ]
        ]
        specs = [
            ("قهوهٔ ترکیبی روزانه", "coffee", 680000, 485000, 0, 20, 40, 5, 3, 5),
            ("روغن زیتون بکر رودبار", "olive", 540000, 395000, 2, 16, 32, 4, 5, 3),
            ("عسل طبیعی کوهستان", "honey", 790000, 590000, 2, 12, 24, 4, 4, 3),
            ("چای بهارهٔ لاهیجان", "tea", 420000, 295000, 0, 20, 40, 5, 2, 2),
            ("زعفران نگین خراسان", "saffron", 640000, 470000, 0, 8, 16, 4, 2, 4),
            ("ماگ دست‌ساز آوند", "ceramic", 380000, 265000, 1, 6, 12, 3, 2, 2),
        ]
        for index, (
            name,
            visual,
            retail,
            price,
            cat,
            minimum,
            capacity,
            limit,
            people,
            qty,
        ) in enumerate(specs):
            product, _ = Product.objects.get_or_create(
                name=name,
                seller=sellers[0] if index < 5 else sellers[1],
                defaults={
                    "category": categories[cat],
                    "retail_price": retail,
                    "unit": "بسته",
                    "visual": visual,
                    "description": (
                        "محصول نمایشی و ساختگی برای ارائهٔ دانشگاهی. "
                        "تهیه‌شده از تولیدکنندهٔ محلی، با بسته‌بندی قابل بازیافت و کیفیت انتخاب‌شده. "
                        "جزئیات ارسال پس از موفقیت کمپین هماهنگ می‌شود."
                    ),
                },
            )
            campaign, created = Campaign.objects.get_or_create(
                product=product,
                title=name,
                defaults={
                    "group_price": price,
                    "min_quantity": minimum,
                    "capacity": capacity,
                    "buyer_limit": limit,
                    "deadline": timezone.now() + timedelta(days=index + 2),
                    "status": "active",
                },
            )
            if created:
                for buyer in buyers[1 : people + 1]:
                    reserve(campaign.pk, buyer, qty)
                if index in (4, 5):
                    campaign.deadline = timezone.now() - timedelta(hours=1)
                    campaign.save(update_fields=["deadline"])
                    settle_campaign(campaign.pk)
        product = Product.objects.get(visual="coffee", seller=sellers[0])
        Campaign.objects.get_or_create(
            title="قهوهٔ تک‌خاستگاه | پیش‌نویس نمونه",
            product=product,
            defaults={
                "group_price": 510000,
                "min_quantity": 10,
                "capacity": 20,
                "buyer_limit": 5,
                "deadline": timezone.now() + timedelta(days=7),
            },
        )
        Campaign.objects.get_or_create(
            title="ظرفیت محدود | سناریوی هم‌زمانی",
            product=product,
            defaults={
                "group_price": 490000,
                "min_quantity": 1,
                "capacity": 1,
                "buyer_limit": 1,
                "deadline": timezone.now() + timedelta(days=7),
                "status": "active",
            },
        )
        self.stdout.write(self.style.SUCCESS("Fictional demo data ready. See docs/SETUP_GUIDE.md."))
