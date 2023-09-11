import base64

from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.fields import SerializerMethodField
from rest_framework.validators import UniqueValidator, UniqueTogetherValidator
from recipe.models import (
    IngredientInRecipe,
    Ingredient,
    Recipe,
    Tag,
    Favorite,
    ShoppingCart,
)
from users.models import User, Follow
from rest_framework.serializers import ModelSerializer


class ImageFieldSerializer(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            format, imgstr = data.split(";base64,")
            ext = format.split("/")[-1]
            data = ContentFile(base64.b64decode(imgstr), name="photo." + ext)

        return super().to_internal_value(data)


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = "__all__"
        read_only_fields = ("__all__",)


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
        )

    def get_is_subscribed(self, object):
        user = self.context.get("request").user
        return (
            not user.is_anonymous
            and Follow.objects.filter(user=user, author=object.id).exists()
        )


class UsersCreateSerializer(serializers.ModelSerializer):
    username = serializers.RegexField(
        regex=r"^[\w.@+-]+\Z",
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())],
        max_length=150,
    )
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())],
        max_length=254,
    )

    class Meta:
        model = User
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "password",
        )
        extra_kwargs = {"password": {"write_only": True}}

    def validate_username(self, value):
        if value == "me":
            raise ValidationError(
                "Невозможно создать пользователя с таким именем!"
            )
        if User.objects.filter(username=value).exists():
            raise ValidationError("Пользователь с таким именем уже существует")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class FollowSerializer(ModelSerializer):
    email = serializers.ReadOnlyField(source="user.email")
    id = serializers.ReadOnlyField(source="user.id")
    username = serializers.ReadOnlyField(source="user.username")
    first_name = serializers.ReadOnlyField(source="user.first_name")
    last_name = serializers.ReadOnlyField(source="user.last_name")
    is_subscribed = serializers.SerializerMethodField()
    recipes_count = SerializerMethodField()
    recipes = SerializerMethodField()

    class Meta:
        model = Follow
        fields = (
            "email",
            "id",
            "username",
            "first_name",
            "last_name",
            "is_subscribed",
            "recipes_count",
            "recipes",
        )
        read_only_fields = ("email", "username")

    def validate(self, data):
        author = self.instance
        user = self.context.get("request").user
        if Follow.objects.filter(author=author, user=user).exists():
            raise ValidationError(
                detail="Вы уже подписаны на этого пользователя!",
                code=status.HTTP_400_BAD_REQUEST,
            )
        if user == author:
            raise ValidationError(
                detail="Вы не можете подписаться на самого себя!",
                code=status.HTTP_400_BAD_REQUEST,
            )
        return data

    def get_is_subscribed(self, object):
        user = object.user
        author = self.context.get("request").user
        return Follow.objects.filter(user=user, author=author).exists()

    def get_recipes_count(self, object):
        return Recipe.objects.filter(author=object.user).count()

    def get_recipes(self, obj):
        recipes = Recipe.objects.filter(author=obj.user)
        serializer = RecipeShortSerializer(recipes, many=True)
        return serializer.data


class RecipeIngredientSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="ingredient.name")
    id = serializers.PrimaryKeyRelatedField(
        source="ingredient.id", read_only=True
    )
    measurement_unit = serializers.CharField(
        source="ingredient.measurement_unit", read_only=True
    )

    class Meta:
        model = IngredientInRecipe
        fields = ("id", "name", "measurement_unit", "amount")
        validators = [
            UniqueTogetherValidator(
                queryset=IngredientInRecipe.objects.all(),
                fields=["ingredient", "recipe"],
            )
        ]


class AddIngredientSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(), source="ingredient"
    )

    class Meta:
        model = IngredientInRecipe
        fields = ("id", "amount")


class RecipeSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    image = ImageFieldSerializer()
    ingredients = AddIngredientSerializer(many=True)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "author",
            "ingredients",
            "name",
            "image",
            "text",
            "cooking_time",
        )
        read_only_fields = ("tags",)

    def tag_validate(self, data):
        tags = self.initial_data.get("tags")
        if not tags:
            raise ValidationError("Укажите хотя бы один тег.")
        if len(tags) != len(set(tags)):
            raise ValidationError("Теги не должны повторяться.")
        for tag in tags:
            get_object_or_404(Tag, pk=tag)
        data[tags] = tags
        return data[tags]

    def ingrtedient_list_validate(self, data):
        ingredients_list = []
        ingredients = self.initial_data.get("ingredients")
        if not ingredients:
            raise ValidationError("Укажите хотя бы один ингредиент.")
        for ingredient in ingredients:
            get_object_or_404(Ingredient, pk=ingredient["id"])
            try:
                int(ingredient["amount"])
            except ValueError:
                raise ValidationError(
                    "Количество ингредиента должно быть записано только в "
                    "виде числа."
                )
            if int(ingredient["amount"]) < 0:
                raise ValidationError("Минимальное количество игредиента - 0.")
            if ingredient in ingredients_list:
                raise ValidationError("Ингредиенты не должны повторяться.")
            ingredients_list.append(ingredient)
        data["ingredients"] = ingredients_list
        return data["ingredients"]

        cooking_time = self.initial_data.get("cooking_time")
        if int(cooking_time) < 1:
            raise ValidationError("Минимальное время приготовления - 1 мин.")
        return data

    @transaction.atomic
    def get_ingredients(self, recipe, ingredients):
        IngredientInRecipe.objects.bulk_create(
            [
                IngredientInRecipe(
                    ingredient=Ingredient.objects.get(id=ingredient["id"]),
                    recipe=recipe,
                    amount=ingredient["amount"],
                )
                for ingredient in ingredients
            ]
        )

    @transaction.atomic
    def create(self, validated_data):
        user = self.context.get("request").user
        tags = validated_data.pop("tags")
        ingredients = validated_data.pop("ingredients")
        recipe = Recipe.objects.create(author=user, **validated_data)
        recipe.tags.set(tags)
        self.get_ingredients(recipe, ingredients)

        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        tags = validated_data.pop("tags")
        ingredients = validated_data.pop("ingredients")

        IngredientInRecipe.objects.filter(recipe=instance).delete()

        instance.tags.set(tags)
        self.get_ingredients(instance, ingredients)

        return super().update(instance, validated_data)

    def to_representation(self, instance):
        request = self.context.get("request")
        context = {"request": request}
        return GetRecipeSerializer(instance, context=context).data


class GetRecipeSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True)
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        read_only=True, many=True, source="recipe_ingredient"
    )
    image = ImageFieldSerializer()
    is_favorited = SerializerMethodField(read_only=True)
    is_in_shopping_cart = SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "tags",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
        )

    def get_is_favorited(self, object):
        user = self.context.get("request").user
        if user.is_anonymous:
            return False
        return user.favorite.filter(recipe=object).exists()

    def get_is_in_shopping_cart(self, object):
        user = self.context.get("request").user
        if user.is_anonymous:
            return False
        return user.shopping_cart.filter(recipe=object).exists()


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ("user", "recipe")

    def validate(self, data):
        user = data.get("user")
        recipe = data.get("recipe")
        if self.Meta.model.objects.filter(user=user, recipe=recipe).exists():
            raise ValidationError({"error": "Этот рецепт уже добавлен"})
        return data

    def to_representation(self, instance):
        context = {"request": self.context.get("request")}
        return RecipeShortSerializer(instance.recipe, context=context).data


class ShoppingCartSerializer(FavoriteSerializer):
    class Meta(FavoriteSerializer.Meta):
        model = ShoppingCart


class RecipeShortSerializer(ModelSerializer):
    image = ImageFieldSerializer()

    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")
