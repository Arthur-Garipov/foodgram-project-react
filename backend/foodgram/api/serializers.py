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
    Follow,
    Favorite,
    ShoppingCart
)
from users.models import User
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
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
        )

    def get_is_subscribed(self, obj):
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Follow.objects.filter(user=user, author=obj).exists()


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
        fields = ("email", "id", "username", "first_name", "last_name", "password")
        extra_kwargs = {"password": {"write_only": True}}

    def validate_username(self, value):
        if value == "me":
            raise ValidationError("Невозможно создать пользователя с таким именем!")
        if User.objects.filter(username=value).exists():
            raise ValidationError("Пользователь с таким именем уже существует")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class FollowSerializer(UserSerializer):
    recipes_count = SerializerMethodField()
    recipes = SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + (
            'recipes_count', 'recipes'
        )
        read_only_fields = ('email', 'username')

    def validate(self, data):
        author = self.instance
        user = self.context.get('request').user
        if Follow.objects.filter(author=author, user=user).exists():
            raise ValidationError(
                detail='Вы уже подписаны на этого пользователя!',
                code=status.HTTP_400_BAD_REQUEST
            )
        if user == author:
            raise ValidationError(
                detail='Вы не можете подписаться на самого себя!',
                code=status.HTTP_400_BAD_REQUEST
            )
        return data

    def get_recipes_count(self, obj):
        return obj.recipes.count()

    def get_recipes(self, obj):
        request = self.context.get('request')
        limit = request.GET.get('recipes_limit')
        recipes = obj.recipes.all()
        if limit:
            recipes = recipes[:int(limit)]
        serializer = RecipeShortSerializer(recipes, many=True, read_only=True)
        return serializer.data


class RecipeIngredientSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="ingredient.name")
    id = serializers.PrimaryKeyRelatedField(source="ingredient.id", read_only=True)
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
            "description",
            "cooking_time",
        )
        read_only_fields = ("tags",)

    def validate(self, data):
        tags = self.initial_data.get("tags")
        if not tags:
            raise ValidationError("Укажите хотя бы один тег.")
        if len(tags) != len(set(tags)):
            raise ValidationError("Теги не должны повторяться.")
        for tag in tags:
            get_object_or_404(Tag, pk=tag)
        data["tags"] = tags

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

        cooking_time = self.initial_data.get("cooking_time")
        if int(cooking_time) < 1:
            raise ValidationError("Минимальное время приготовления - 1 мин.")
        return data

    @transaction.atomic
    def get_ingredients(self, recipe, ingredients):
        IngredientInRecipe.objects.bulk_create(
            [
                IngredientInRecipe(
                    ingredient=ingredient.get("ingredient"),
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
    ingredients = RecipeIngredientSerializer(read_only=True, many=True,
                                             source="recipe_ingredient")
    image = ImageFieldSerializer()
    favorited = SerializerMethodField(read_only=True)
    is_in_shopping_cart = SerializerMethodField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            "id",
            "tags",
            "author",
            "ingredients",
            "favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "description",
            "cooking_time",
        )

    def get_favorited(self, object):
        user = self.context.get("request").user
        if user.is_anonymous:
            return False
        return object.favorite.filter(user=user).exists()

    def get_is_in_shopping_cart(self, object):
        user = self.context.get("request").user
        if user.is_anonymous:
            return False
        return object.is_in_shopping_cart.filter(user=user).exists()


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ("user", "recipe")

    def validate(self, data):
        user, recipe = data.get("user"), data.get("recipe")
        if self.Meta.model.objects.filter(user=user, recipe=recipe).exists():
            raise ValidationError(
                {"error": "Этот рецепт уже добавлен"}
            )
        return data


class ShoppingCartSerializer(FavoriteSerializer):
    class Meta(FavoriteSerializer.Meta):
        model = ShoppingCart

class RecipeShortSerializer(ModelSerializer):
    image = ImageFieldSerializer()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'name',
            'image',
            'cooking_time'
        )
