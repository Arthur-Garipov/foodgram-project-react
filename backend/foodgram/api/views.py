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
    UserCreateSerializer,
    FollowSerializer,
    TagSerializer,
)
from .permissions import IsAuthorOrReadOnly, CustomUserPermissions
from rest_framework import viewsets, status, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from django.db import IntegrityError
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.exceptions import ValidationError


class UserViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "patch", "delete"]
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ("username",)
    lookup_field = "username"
    pagination_class = CustomPagination

    @action(
        methods=(
            "GET",
            "PATCH",
            "POST"
        ),
        detail=False,
        url_path="me",
        permission_classes=(IsAuthenticated, CustomUserPermissions,),
    )
    def user_own_account(self, request):
        user = request.user
        if request.method == "GET":
            serializer = self.get_serializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(role=user.role, partial=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=["POST", "DELETE"], detail=True)
    def subscribe(self, request, id):
        user = request.user
        author = get_object_or_404(User, id=id)
        subscription = Follow.objects.filter(user=user, author=author)

        if request.method == "POST":
            if subscription.exists():
                return Response(
                    {"error": "Вы уже подписаны"}, status=status.HTTP_400_BAD_REQUEST
                )
            if user == author:
                return Response(
                    {"error": "Невозможно подписаться на себя"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer = FollowSerializer(author, context={"request": request})
            Follow.objects.create(user=user, author=author)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "DELETE":
            if subscription.exists():
                subscription.delete()
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(
                {"error": "Вы не подписаны на этого пользователя"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, permission_classes=[IsAuthenticated])
    def subscriptions(self, request):
        user = request.user
        follows = User.objects.filter(following__user=user)
        page = self.paginate_queryset(follows)
        serializer = FollowSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    @action(detail=False, permission_classes=[AllowAny])
    def signup(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        email = serializer.validated_data["email"]
        try:
            user, created = User.objects.get_or_create(username=username, email=email)
            confirmation_code = default_token_generator.make_token(user)
            send_mail(
                "Код подтверждения",
                f"Ваш код подтверждения: {confirmation_code}",
                [user.email],
                fail_silently=False,
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        except IntegrityError:
            raise ValidationError(
                "Данные имя пользователя или Email уже зарегистрированы"
            )

    @action(detail=False, permission_classes=[AllowAny])
    def get_token(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        confirmation_code = serializer.validated_data["confirmation_code"]
        user = get_object_or_404(User, username=username)
        if default_token_generator.check_token(user, confirmation_code):
            token = str(AccessToken.for_user(user))
            return Response({"token": token}, status=status.HTTP_200_OK)
        raise ValidationError("Введен неверный код.")


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
