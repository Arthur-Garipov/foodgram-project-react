from django.contrib.auth import get_user_model
from django.core.validators import (
    MinValueValidator,
    RegexValidator,
    MaxValueValidator,
)
from django.db import models
from django.db.models import UniqueConstraint

User = get_user_model()


class Ingredient(models.Model):
    name = models.CharField(
        verbose_name="Название ингредиента", max_length=100
    )
    measurement_unit = models.CharField(
        verbose_name="Единица измерения", max_length=15
    )

    class Meta:
        verbose_name = "Ингредиент"
        verbose_name_plural = "Ингредиенты"
        unique_together = ('name', 'measurement_unit')

    def __str__(self):
        return f"{self.name}, {self.measurement_unit}"


class Tag(models.Model):
    name = models.CharField(
        verbose_name="Название", max_length=16, unique=True
    )
    color = models.CharField(
        "Цветовой HEX-код",
        unique=True,
        max_length=7,
        validators=[
            RegexValidator(
                regex="^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$",
                message="Введенное значение не является цветом в формате HEX!",
            )
        ],
    )
    slug = models.SlugField("Уникальный слаг", unique=True, max_length=200)

    class Meta:
        verbose_name = "Тег"

    def __str__(self):
        return f"{self.name}"


class Recipe(models.Model):
    name = models.CharField(
        max_length=100,
        verbose_name="Название",
        help_text="Введите название блюда",
    )
    author = models.ForeignKey(
        User, related_name="recipe", on_delete=models.CASCADE
    )
    image = models.ImageField(
        upload_to="recipe/",
        help_text="Выберите фотографию готового блюда",
        blank=True,
    )
    pub_date = models.DateTimeField(
        verbose_name="Дата публикации", auto_now_add=True
    )
    text = models.TextField(verbose_name="Описание рецепта")
    ingredients = models.ManyToManyField(
        Ingredient,
        verbose_name="Ингредиенты",
        through="IngredientInRecipe",
    )
    tags = models.ManyToManyField(Tag, related_name="recipe")
    cooking_time = models.PositiveSmallIntegerField(
        verbose_name="Время приготовления",
        validators=[
            MinValueValidator(
                limit_value=1,
                message=(
                    "Время приготовления не может быть менее одной минуты."
                ),
            ),
            MaxValueValidator(
                limit_value=2880,
                message=("Время приготовления не может быть более 2-х суток."),
            ),
        ],
    )

    class Meta:
        ordering = ["-pub_date"]
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"

    def __str__(self):
        return f"{self.name[:50]}"


class IngredientInRecipe(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name="Рецепт",
        related_name="recipe_ingredient",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name="Ингредиент",
    )
    amount = models.PositiveSmallIntegerField(
        verbose_name="Количество",
        validators=(
            MinValueValidator(
                limit_value=1, message="Количество должно быть меньше нуля"
            ),
        ),
    )

    class Meta:
        verbose_name = "Ингредиент в рецепте"
        constraints = [
            UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="unique ingredient for recipe",
            )
        ]

    def __str__(self):
        return (
            f"{self.recipe}: {self.ingredient.name},"
            f" {self.amount}, {self.ingredient.measurement_unit}"
        )


class BaseFavShopModel(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name="Рецепты",
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.recipe} добавлен пользователем {self.user}"


class Favorite(BaseFavShopModel):
    class Meta:
        verbose_name = "Избранный рецепт"
        verbose_name_plural = "Избранные рецепты"
        constraints = [
            UniqueConstraint(
                fields=["user", "recipe"], name="unique favorite"
            ),
        ]


class ShoppingCart(BaseFavShopModel):
    class Meta:
        verbose_name = "Рецепт в корзине"
        constraints = [
            UniqueConstraint(
                fields=["user", "recipe"],
                name="unique recipe in shopping cart",
            ),
        ]
