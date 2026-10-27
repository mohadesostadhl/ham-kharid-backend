from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from django.forms import ModelForm
from django.utils import timezone

from .exceptions import BusinessError
from .models import Campaign, Category, Order, Product, Reservation, User
from .services import advance_order, cancel_reservation, publish_campaign, settle_campaign

admin.site.site_header = "Hamkharid administration"
admin.site.site_title = "Hamkharid admin"
admin.site.index_title = "Marketplace management"


@admin.register(User)
class MarketplaceUserAdmin(UserAdmin):
    fieldsets = (*UserAdmin.fieldsets, ("Marketplace", {"fields": ("display_name", "role")}))
    add_fieldsets = (
        *UserAdmin.add_fieldsets,
        ("Marketplace", {"fields": ("display_name", "role")}),
    )
    list_display = ("username", "display_name", "email", "role", "is_staff", "is_active")
    list_filter = (*UserAdmin.list_filter, "role")
    search_fields = (*UserAdmin.search_fields, "display_name")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "seller", "category", "retail_price", "unit")
    list_filter = ("category", "visual")
    search_fields = ("name", "description", "seller__username")
    autocomplete_fields = ("seller", "category")
    readonly_fields = ("created_at",)
    list_select_related = ("seller", "category")


def run_action(model_admin, request, queryset, operation):
    completed = 0
    for obj in queryset:
        try:
            if operation(obj):
                completed += 1
        except BusinessError as exc:
            model_admin.message_user(request, f"#{obj.pk}: {exc}", level=messages.ERROR)
    model_admin.message_user(request, f"Updated {completed} record(s).", level=messages.INFO)


class CampaignAdminForm(ModelForm):
    class Meta:
        model = Campaign
        fields = "__all__"

    def clean(self):
        data = super().clean()
        product = data.get("product")
        price = data.get("group_price")
        if product and price and price >= product.retail_price:
            self.add_error("group_price", "Group price must be below the retail price.")
        deadline = data.get("deadline")
        if deadline and deadline <= timezone.now():
            self.add_error("deadline", "The deadline must be in the future.")
        if product and product.seller.role != User.Role.SELLER:
            raise ValidationError("The product must belong to a seller.")
        return data


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    form = CampaignAdminForm
    list_display = (
        "title",
        "product",
        "status",
        "group_price",
        "reserved_quantity",
        "capacity",
        "deadline",
    )
    list_filter = ("status", "deadline")
    search_fields = ("title", "product__name", "product__seller__username")
    autocomplete_fields = ("product",)
    readonly_fields = ("status", "reserved_quantity", "created_at")
    list_select_related = ("product",)
    actions = ("publish", "settle")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status != Campaign.Status.DRAFT:
            return tuple(field.name for field in self.model._meta.fields)
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Publish selected drafts", permissions=["change"])
    def publish(self, request, queryset):
        run_action(
            self, request, queryset, lambda obj: publish_campaign(obj.pk, obj.product.seller)
        )

    @admin.action(
        description="Settle selected campaigns past their deadline", permissions=["change"]
    )
    def settle(self, request, queryset):
        run_action(self, request, queryset, lambda obj: settle_campaign(obj.pk))


class TransactionAdmin(admin.ModelAdmin):
    """Transactional records are created by services and modified only through actions."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Reservation)
class ReservationAdmin(TransactionAdmin):
    list_display = ("id", "buyer", "campaign", "quantity", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("buyer__username", "campaign__title")
    list_select_related = ("buyer", "campaign")
    actions = ("cancel",)

    @admin.action(description="Cancel selected active reservations", permissions=["change"])
    def cancel(self, request, queryset):
        run_action(self, request, queryset, lambda obj: cancel_reservation(obj.pk, obj.buyer))


@admin.register(Order)
class OrderAdmin(TransactionAdmin):
    list_display = ("id", "reservation", "unit_price", "quantity", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("reservation__buyer__username", "reservation__campaign__title")
    list_select_related = ("reservation__campaign__product__seller",)
    actions = ("ship", "complete")

    def advance(self, request, queryset, status):
        run_action(
            self,
            request,
            queryset,
            lambda obj: advance_order(obj.pk, obj.reservation.campaign.product.seller, status),
        )

    @admin.action(description="Mark selected confirmed orders as shipped", permissions=["change"])
    def ship(self, request, queryset):
        self.advance(request, queryset, Order.Status.SHIPPED)

    @admin.action(description="Mark selected shipped orders as completed", permissions=["change"])
    def complete(self, request, queryset):
        self.advance(request, queryset, Order.Status.COMPLETED)
