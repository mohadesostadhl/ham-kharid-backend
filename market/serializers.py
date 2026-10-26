from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import Campaign, Category, Order, Product, Reservation, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "display_name", "role"]


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    class Meta:
        model = User
        fields = ["username", "display_name", "role", "password"]
        extra_kwargs = {"display_name": {"required": True, "allow_blank": False}}

    def validate(self, attrs):
        try:
            validate_password(
                attrs["password"], User(**{k: v for k, v in attrs.items() if k != "password"})
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductSerializer(serializers.ModelSerializer):
    retail_price = serializers.IntegerField(min_value=1, max_value=10_000_000_000)
    seller_name = serializers.CharField(source="seller.display_name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "category",
            "category_name",
            "retail_price",
            "unit",
            "visual",
            "seller_name",
        ]


class CampaignSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product", queryset=Product.objects.all(), write_only=True
    )
    progress = serializers.SerializerMethodField()
    participant_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Campaign
        fields = [
            "id",
            "title",
            "product",
            "product_id",
            "group_price",
            "min_quantity",
            "capacity",
            "buyer_limit",
            "reserved_quantity",
            "deadline",
            "status",
            "progress",
            "participant_count",
        ]
        read_only_fields = ["reserved_quantity", "status"]

    def get_progress(self, obj):
        return min(100, round(obj.reserved_quantity / obj.min_quantity * 100))

    def validate(self, attrs):
        product = attrs["product"]
        if product.seller_id != self.context["request"].user.pk:
            raise serializers.ValidationError({"product_id": "فقط محصول خودتان را انتخاب کنید."})
        if attrs["deadline"] <= timezone.now():
            raise serializers.ValidationError({"deadline": "مهلت باید در آینده باشد."})
        if attrs["group_price"] <= 0 or attrs["group_price"] >= product.retail_price:
            raise serializers.ValidationError(
                {"group_price": "قیمت گروهی باید کمتر از قیمت تکی باشد."}
            )
        if not 1 <= attrs["min_quantity"] <= attrs["capacity"]:
            raise serializers.ValidationError(
                {"min_quantity": "حدنصاب باید بین ۱ و ظرفیت کل باشد."}
            )
        if not 1 <= attrs["buyer_limit"] <= attrs["capacity"]:
            raise serializers.ValidationError(
                {"buyer_limit": "سقف خریدار باید بین ۱ و ظرفیت کل باشد."}
            )
        return attrs


class ReservationSerializer(serializers.ModelSerializer):
    campaign = CampaignSerializer(read_only=True)

    class Meta:
        model = Reservation
        fields = ["id", "campaign", "quantity", "status", "created_at"]


class ReserveSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=100000)


class OrderSerializer(serializers.ModelSerializer):
    campaign_title = serializers.CharField(source="reservation.campaign.title", read_only=True)
    campaign_id = serializers.IntegerField(source="reservation.campaign_id", read_only=True)
    buyer_name = serializers.CharField(source="reservation.buyer.display_name", read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "campaign_id",
            "campaign_title",
            "buyer_name",
            "unit_price",
            "quantity",
            "total",
            "status",
            "created_at",
        ]

    def get_total(self, obj):
        return obj.quantity * obj.unit_price


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)
