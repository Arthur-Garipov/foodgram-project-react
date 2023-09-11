from django.contrib import admin
from .models import (
    Ingredient,
    Recipe,
    Tag,
    IngredientInRecipe,
    Favorite,
    ShoppingCart,
)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "measurement_unit",
    )
    search_fields = ("name",)
    list_filter = ("name",)
    empty_value_display = "-пусто-"


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "slug")


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("name", "author", "pub_date", "display_tags", "favorite")
    list_filter = ("name", "author", "tags")
    search_fields = ("name",)
    readonly_fields = ("favorite",)
    fields = (
        "image",
        ("name", "author"),
        "text",
        ("tags", "cooking_time"),
        "favorite",
    )

    def display_tags(self, obj):
        return ", ".join([tag.name for tag in obj.tags.all()])

    display_tags.short_description = "Теги"

    def favorite(self, obj):
        return obj.favorite.count()

    favorite.short_description = "B избранном"


@admin.register(IngredientInRecipe)
class IngredientInRecipeAdmin(admin.ModelAdmin):
    list_display = ("recipe", "ingredient", "amount")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("recipe", "user")


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ("recipe", "user")
