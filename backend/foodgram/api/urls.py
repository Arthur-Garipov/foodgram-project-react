from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import IngredientViewSet, RecipeViewSet, TagViewSet, UserViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"ingredients", IngredientViewSet)
router.register(r"recipes", RecipeViewSet)
router.register(r"tags", TagViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path('', include('djoser.urls')),
    path("auth/", include("djoser.urls.authtoken")),
]
