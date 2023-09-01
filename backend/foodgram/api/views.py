from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import IntegrityError
from django.contrib.auth.tokens import default_token_generator
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from recipe.models import Ingredient, Recipe, Tag, Follow
from users.models import User
from .paginate import CustomPagination
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.pdfbase import pdfmetrics, ttfonts
from reportlab.pdfgen import canvas
from .filters import RecipeFilter, IngredientFilter
from .serializers import (
    IngredientSerializer,
    RecipeSerializer,
    UserSerializer,
    FollowSerializer,
    TagSerializer,
)
from djoser.views import UserViewSet
from .permissions import IsAuthorOrReadOnly
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
# from django.core.mail import send_mail
# from django.contrib.auth.tokens import default_token_generator
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly


class UserViewSet(UserViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = CustomPagination

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, **kwargs):
        user = request.user
        author_id = self.kwargs.get('id')
        author = get_object_or_404(User, id=author_id)

        if request.method == 'POST':
            serializer = FollowSerializer(author,
                                             data=request.data,
                                             context={"request": request})
            serializer.is_valid(raise_exception=True)
            Follow.objects.create(user=user, author=author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            subscription = get_object_or_404(Follow,
                                             user=user,
                                             author=author)
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        permission_classes=[IsAuthenticated]
    )
    def subscriptions(self, request):
        user = request.user
        queryset = User.objects.filter(subscribing__user=user)
        pages = self.paginate_queryset(queryset)
        serializer = FollowSerializer(pages,
                                         many=True,
                                         context={'request': request})
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
    serializer_class = RecipeSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    permission_classes = (IsAuthorOrReadOnly,)
    pagination_class = CustomPagination

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
        return self.action_post_delete(pk)

    @action(methods=["POST", "DELETE"], detail=True)
    def shopping_cart(self, request, pk):
        return self.action_post_delete(pk)

    @action(detail=False)
    def download_shopping_cart(self, request):
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = "attachment; filename='shopping_cart.pdf'"
        p = canvas.Canvas(response)
        arial = ttfonts.TTFont("Arial", "data/arial.ttf")
        pdfmetrics.registerFont(arial)
        p.setFont("Arial", 14)

        ingredients = Ingredient.objects.filter(
            recipe__shopping_cart__user=request.user
        ).values_list("ingredient__name", "amount", "ingredient__measurement_unit")

        ingr_list = {}
        for name, amount, unit in ingredients:
            if name not in ingr_list:
                ingr_list[name] = {"amount": amount, "unit": unit}
            else:
                ingr_list[name]["amount"] += amount
        height = 700

        p.drawString(100, 750, "Список покупок")
        for i, (name, data) in enumerate(ingr_list.items(), start=1):
            p.drawString(80, height, f"{i}. {name} – {data['amount']} {data['unit']}")
            height -= 25
        p.showPage()
        p.save()
        return response
