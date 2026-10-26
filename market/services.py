from django.db import transaction
from django.utils import timezone

from .exceptions import BusinessError
from .models import Campaign, Order, Reservation, User


def require_seller(user: User) -> None:
    if user.role != User.Role.SELLER:
        raise BusinessError("این بخش ویژهٔ فروشندگان است.")


def require_owner(campaign: Campaign, user: User) -> None:
    require_seller(user)
    if campaign.product.seller_id != user.pk:
        raise BusinessError("شما اجازهٔ مدیریت این کمپین را ندارید.")


def update_threshold(campaign: Campaign) -> None:
    campaign.status = (
        Campaign.Status.FUNDED
        if campaign.reserved_quantity >= campaign.min_quantity
        else Campaign.Status.ACTIVE
    )
    campaign.save(update_fields=["status", "reserved_quantity"])


@transaction.atomic
def publish_campaign(campaign_id: int, seller: User) -> Campaign:
    campaign = Campaign.objects.select_for_update().select_related("product").get(pk=campaign_id)
    require_owner(campaign, seller)
    if campaign.status != Campaign.Status.DRAFT or campaign.deadline <= timezone.now():
        raise BusinessError("فقط پیش‌نویس دارای مهلت معتبر قابل انتشار است.")
    campaign.status = Campaign.Status.ACTIVE
    campaign.save(update_fields=["status"])
    return campaign


@transaction.atomic
def reserve(campaign_id: int, buyer: User, quantity: int) -> Reservation:
    if buyer.role != User.Role.BUYER:
        raise BusinessError("رزرو فقط برای حساب خریدار امکان‌پذیر است.")
    # SQLite BEGIN IMMEDIATE acquires the write lock before reading capacity.
    # select_for_update also keeps this safe if later migrated to PostgreSQL.
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    if campaign.status not in (Campaign.Status.ACTIVE, Campaign.Status.FUNDED):
        raise BusinessError("این کمپین برای رزرو باز نیست.")
    if campaign.deadline <= timezone.now():
        raise BusinessError("مهلت رزرو این کمپین پایان یافته است.")
    reservation = Reservation.objects.filter(campaign=campaign, buyer=buyer).first()
    previous = reservation.quantity if reservation and reservation.status == "active" else 0
    if quantity <= 0 or quantity + previous > campaign.buyer_limit:
        raise BusinessError(f"سقف رزرو هر خریدار {campaign.buyer_limit} واحد است.")
    if campaign.reserved_quantity + quantity > campaign.capacity:
        raise BusinessError("ظرفیت باقی‌مانده برای این تعداد کافی نیست.")
    if reservation:
        reservation.quantity = previous + quantity
        reservation.status = Reservation.Status.ACTIVE
        reservation.save(update_fields=["quantity", "status", "updated_at"])
    else:
        reservation = Reservation.objects.create(buyer=buyer, campaign=campaign, quantity=quantity)
    campaign.reserved_quantity += quantity
    update_threshold(campaign)
    return reservation


@transaction.atomic
def cancel_reservation(reservation_id: int, buyer: User) -> Reservation:
    existing = Reservation.objects.get(pk=reservation_id, buyer=buyer)
    campaign = Campaign.objects.select_for_update().get(pk=existing.campaign_id)
    reservation = Reservation.objects.select_for_update().get(pk=existing.pk)
    if campaign.deadline <= timezone.now() or campaign.status not in ("active", "funded"):
        raise BusinessError("پس از پایان کمپین امکان لغو رزرو وجود ندارد.")
    if reservation.status != Reservation.Status.ACTIVE:
        raise BusinessError("این رزرو فعال نیست.")
    reservation.status = Reservation.Status.CANCELLED
    reservation.save(update_fields=["status", "updated_at"])
    campaign.reserved_quantity -= reservation.quantity
    update_threshold(campaign)
    return reservation


@transaction.atomic
def settle_campaign(campaign_id: int) -> bool:
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    if campaign.status not in ("active", "funded") or campaign.deadline > timezone.now():
        return False
    successful = campaign.reserved_quantity >= campaign.min_quantity
    for reservation in campaign.reservations.filter(status=Reservation.Status.ACTIVE):
        if successful:
            Order.objects.get_or_create(
                reservation=reservation,
                defaults={"unit_price": campaign.group_price, "quantity": reservation.quantity},
            )
        reservation.status = "converted" if successful else "released"
        reservation.save(update_fields=["status", "updated_at"])
    campaign.status = Campaign.Status.SUCCESSFUL if successful else Campaign.Status.FAILED
    campaign.save(update_fields=["status"])
    return True


@transaction.atomic
def advance_order(order_id: int, seller: User, status: str) -> Order:
    order = (
        Order.objects.select_for_update()
        .select_related("reservation__campaign__product")
        .get(pk=order_id)
    )
    require_owner(order.reservation.campaign, seller)
    transitions = {"confirmed": "shipped", "shipped": "completed"}
    if transitions.get(order.status) != status:
        raise BusinessError("تغییر وضعیت سفارش معتبر نیست.")
    order.status = status
    order.save(update_fields=["status"])
    return order
