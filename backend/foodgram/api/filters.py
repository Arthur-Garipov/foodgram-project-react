from django.db.models import BooleanField, ExpressionWrapper, Q
from django_filters import FilterSet, filters

from recipe.models import Ingredient, Recipe


class IngredientFilter(FilterSet):
    name = filters.CharFilter(method="filter_name")

    class Meta:
        model = Ingredient
        fields = ("name",)

    def filter_name(self, queryset, name, value):
        return (
            queryset.filter(Q(name__istartswith=value) | Q(name__icontains=value))
            .annotate(
                startswith=ExpressionWrapper(
                    Q(name__istartswith=value), output_field=BooleanField()
                )
            )
            .order_by("-startswith")
        )


class RecipeFilter(FilterSet):
    author = filters.CharFilter(field_name="author__id")
    tags = filters.AllValuesMultipleFilter(field_name="tags__slug")
    is_favorited = filters.NumberFilter(method="filter_is_favorited")
    is_in_shopping_cart = filters.NumberFilter(method="filter_is_in_shopping_cart")

    class Meta:
        model = Recipe
        fields = ("author", "tags", "is_favorited", "is_in_shopping_cart")

    def filter_is_favorited(self, queryset, name, value):
        if value and self.request.user.is_authenticated:
            return queryset.filter(favorite__user=self.request.user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        if value and not self.request.user.is_anonymous:
            return queryset.filter(shopping_cart__user=self.request.user)
        return queryset
