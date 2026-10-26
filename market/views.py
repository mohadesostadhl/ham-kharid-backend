from django.contrib.auth import authenticate, login, logout
from django.db import connection
from django.db.models import Count, Q
from django.http import Http404
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import serializers as s
from . import services
from .exceptions import BusinessError
from .models import Campaign, Category, Order, Product, Reservation


class SessionView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response(
            {
                "user": s.UserSerializer(request.user).data
                if request.user.is_authenticated
                else None,
                "csrf_token": get_token(request),
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = s.LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(request, **serializer.validated_data)
        if not user:
            raise BusinessError("نام کاربری یا رمز عبور درست نیست.")
        login(request, user)
        return Response({"user": s.UserSerializer(user).data, "csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class SignupView(LoginView):
    def post(self, request):
        serializer = s.SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(
            {"user": s.UserSerializer(user).data, "csrf_token": get_token(request)}, status=201
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"user": None, "csrf_token": get_token(request)})


class HealthView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return Response({"status": "ok", "database": connection.vendor})


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = s.CategorySerializer
    pagination_class = None


class ProductViewSet(viewsets.GenericViewSet):
    serializer_class = s.ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Product.objects.select_related("seller", "category")

    def get_queryset(self):
        return super().get_queryset().filter(seller=self.request.user)

    def list(self, request):
        services.require_seller(request.user)
        return Response(self.get_serializer(self.get_queryset(), many=True).data)

    def create(self, request):
        services.require_seller(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(seller=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CampaignViewSet(viewsets.GenericViewSet):
    serializer_class = s.CampaignSerializer
    queryset = Campaign.objects.select_related("product__seller", "product__category").annotate(
        participant_count=Count(
            "reservations", filter=Q(reservations__status__in=["active", "converted"])
        )
    )

    def get_queryset(self):
        queryset = super().get_queryset().order_by("-id")
        if self.request.query_params.get("mine") == "1":
            if not self.request.user.is_authenticated:
                return queryset.none()
            return queryset.filter(product__seller=self.request.user)
        return queryset.exclude(status="draft")

    def list(self, request):
        queryset = self.get_queryset()
        category = request.query_params.get("category")
        if category:
            queryset = queryset.filter(product__category__slug=category)
        search = request.query_params.get("search", "")[:150]
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(product__name__icontains=search)
            )
        if request.query_params.get("status") in Campaign.Status.values:
            queryset = queryset.filter(status=request.query_params["status"])
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def create(self, request):
        services.require_seller(request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def publish(self, request, pk=None):
        campaign = self.queryset.filter(pk=pk, product__seller=request.user).first()
        if not campaign:
            raise Http404
        return Response(
            self.get_serializer(services.publish_campaign(campaign.pk, request.user)).data
        )

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def reserve(self, request, pk=None):
        campaign = self.get_object()
        serializer = s.ReserveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reservation = services.reserve(campaign.pk, request.user, **serializer.validated_data)
        return Response(s.ReservationSerializer(reservation).data, status=201)


class ReservationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = s.ReservationSerializer
    pagination_class = None

    def get_queryset(self):
        return Reservation.objects.filter(buyer=self.request.user).select_related(
            "campaign__product__seller", "campaign__product__category"
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        reservation = self.get_object()
        result = services.cancel_reservation(reservation.pk, request.user)
        return Response(self.get_serializer(result).data)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = s.OrderSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = Order.objects.select_related(
            "reservation__campaign__product", "reservation__buyer"
        )
        if self.request.user.role == "seller":
            return queryset.filter(reservation__campaign__product__seller=self.request.user)
        return queryset.filter(reservation__buyer=self.request.user)

    @action(detail=True, methods=["post"], url_path="status")
    def change_status(self, request, pk=None):
        order = self.get_object()
        serializer = s.OrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = services.advance_order(order.pk, request.user, serializer.validated_data["status"])
        return Response(self.get_serializer(result).data)
