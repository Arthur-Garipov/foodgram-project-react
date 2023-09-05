from datetime import datetime
from django.db.models import Sum
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from recipe.models import Ingredient, Recipe, Tag, Follow, IngredientInRecipe
from users.models import User
from .paginate import CustomPagination
from django.http import HttpResponse
from rest_framework.status import HTTP_400_BAD_REQUEST
from django.shortcuts import get_object_or_404
from .filters import RecipeFilter, IngredientFilter
from .serializers import (
    IngredientSerializer,
    RecipeSerializer,
    GetRecipeSerializer,
    UserSerializer,
    FollowSerializer,
    TagSerializer,
    FavoriteSerializer,
    ShoppingCartSerializer,
)
from djoser.views import UserViewSet
from .permissions import IsAuthorOrReadOnly
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, SAFE_METHODS


class UserViewSet(UserViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = CustomPagination

    @action(
        detail=True, methods=["post", "delete"], permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, **kwargs):
        user = request.user
        author_id = self.kwargs.get("id")
        author = get_object_or_404(User, id=author_id)

        if request.method == "POST":
            serializer = FollowSerializer(
                author, data=request.data, context={"request": request}
            )
            serializer.is_valid(raise_exception=True)
            Follow.objects.create(user=user, author=author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "DELETE":
            subscription = get_object_or_404(Follow, user=user, author=author)
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        user = request.user
        queryset = User.objects.filter(subscribing__user=user)
        pages = self.paginate_queryset(queryset)
        serializer = FollowSerializer(pages, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    permission_classes = (AllowAny,)
    pagination_class = None


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)
    pagination_class = None


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    permission_classes = (IsAuthorOrReadOnly,)
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return GetRecipeSerializer
        return RecipeSerializer

    def action_post_delete(self, pk, serializer_class):
        user = self.request.user
        recipe = get_object_or_404(Recipe, pk=pk)
        object = serializer_class.Meta.model.objects.filter(user=user, recipe=recipe)

        if self.request.method == "POST":
            serializer = serializer_class(
                data={"user": user.id, "recipe": pk}, context={"request": self.request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if self.request.method == "DELETE":
            if object.exists():
                object.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                {"error": "Этого рецепта нет в списке"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(methods=["POST", "DELETE"], detail=True)
    def favorite(self, request, pk):
        return self.action_post_delete(pk, FavoriteSerializer)

    @action(methods=["POST", "DELETE"], detail=True)
    def shopping_cart(self, request, pk):
        return self.action_post_delete(pk, ShoppingCartSerializer)

    @action(detail=False, permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user
        if not user.shopping_cart.exists():
            return Response(status=HTTP_400_BAD_REQUEST)

        ingredients = (
            IngredientInRecipe.objects.filter(recipe__shopping_cart__user=request.user)
            .values("ingredient__name", "ingredient__measurement_unit")
            .annotate(amount=Sum("amount"))
        )

        today = datetime.today()
        shopping_list = (
            f"Список покупок для: {user.get_full_name()}\n\n"
            f"Дата: {today:%Y-%m-%d}\n\n"
        )
        shopping_list += "\n".join(
            [
                f'- {ingredient["ingredient__name"]} '
                f'({ingredient["ingredient__measurement_unit"]})'
                f' - {ingredient["amount"]}'
                for ingredient in ingredients
            ]
        )
        shopping_list += f"\n\nFoodgram ({today:%Y})"

        filename = f"{user.username}_shopping_list.txt"
        response = HttpResponse(shopping_list, content_type="text/plain")
        response["Content-Disposition"] = f"attachment; filename={filename}"

        return response
