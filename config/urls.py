from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from market import views

router = DefaultRouter()
router.register("categories", views.CategoryViewSet)
router.register("products", views.ProductViewSet)
router.register("campaigns", views.CampaignViewSet)
router.register("reservations", views.ReservationViewSet, basename="reservation")
router.register("orders", views.OrderViewSet, basename="order")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", views.HealthView.as_view()),
    path("api/auth/session/", views.SessionView.as_view()),
    path("api/auth/login/", views.LoginView.as_view()),
    path("api/auth/signup/", views.SignupView.as_view()),
    path("api/auth/logout/", views.LogoutView.as_view()),
    path("api/wallet/", views.WalletView.as_view()),
    path("api/", include(router.urls)),
]
