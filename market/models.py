from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q


class User(AbstractUser):
    class Role(models.TextChoices):
        BUYER = "buyer", "خریدار"
        SELLER = "seller", "فروشنده"

    role = models.CharField(max_length=10, choices=Role, default=Role.BUYER)
    display_name = models.CharField(max_length=100)
    wallet_balance = models.PositiveBigIntegerField(default=0)


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["id"]


class Product(models.Model):
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    name = models.CharField(max_length=150)
    description = models.TextField(max_length=3000)
    retail_price = models.PositiveBigIntegerField()
    unit = models.CharField(max_length=30, default="عدد")
    visual = models.CharField(
        max_length=20,
        choices=[(v, v) for v in ["coffee", "olive", "honey", "tea", "saffron", "ceramic"]],
        default="coffee",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=Q(retail_price__gt=0), name="retail_positive")
        ]


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        ACTIVE = "active", "در حال جمع‌آوری"
        FUNDED = "funded", "حدنصاب تکمیل شد"
        SUCCESSFUL = "successful", "موفق"
        FAILED = "failed", "ناموفق"

    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="campaigns")
    title = models.CharField(max_length=160)
    group_price = models.PositiveBigIntegerField()
    min_quantity = models.PositiveIntegerField()
    capacity = models.PositiveIntegerField()
    buyer_limit = models.PositiveIntegerField(default=5)
    reserved_quantity = models.PositiveIntegerField(default=0)
    deadline = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=Q(group_price__gt=0), name="group_price_positive"),
            models.CheckConstraint(condition=Q(min_quantity__gt=0), name="threshold_positive"),
            models.CheckConstraint(
                condition=Q(capacity__gte=F("min_quantity")), name="capacity_min"
            ),
            models.CheckConstraint(condition=Q(buyer_limit__gt=0), name="buyer_limit_positive"),
            models.CheckConstraint(
                condition=Q(buyer_limit__lte=F("capacity")), name="limit_capacity"
            ),
            models.CheckConstraint(
                condition=Q(reserved_quantity__lte=F("capacity")), name="no_oversell"
            ),
        ]


class Reservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "فعال"
        CANCELLED = "cancelled", "لغوشده"
        CONVERTED = "converted", "تبدیل به سفارش"
        RELEASED = "released", "آزادشده"

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="reservations")
    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveBigIntegerField(default=0)
    paid_amount = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(fields=["buyer", "campaign"], name="one_buyer_campaign"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="reservation_positive"),
        ]


class Order(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "تأییدشده"
        SHIPPED = "shipped", "ارسال‌شده"
        COMPLETED = "completed", "تحویل‌شده"

    reservation = models.OneToOneField(Reservation, on_delete=models.PROTECT)
    unit_price = models.PositiveBigIntegerField()
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status, default=Status.CONFIRMED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class WalletTransaction(models.Model):
    class Kind(models.TextChoices):
        TOP_UP = "top_up", "شارژ نمایشی"
        PAYMENT = "payment", "پرداخت رزرو"
        REFUND = "refund", "بازگشت وجه"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reservation = models.ForeignKey(Reservation, on_delete=models.PROTECT, null=True, blank=True)
    kind = models.CharField(max_length=10, choices=Kind)
    amount = models.BigIntegerField()
    balance_after = models.PositiveBigIntegerField()
    reference = models.UUIDField(unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(kind="payment", amount__lt=0) | Q(kind__in=["top_up", "refund"], amount__gt=0)
                ),
                name="wallet_transaction_direction",
            ),
        ]
