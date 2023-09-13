import csv

from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from recipe.models import Ingredient


ContentType.objects.all().delete()


class Command(BaseCommand):
    def handle(self, *args, **options):
        with open("recipe/data/ingredients.csv", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                name, measurement_unit = row
                Ingredient.objects.get_or_create(
                    name=name, measurement_unit=measurement_unit
                )
                self.stdout.write(f"{name}, {measurement_unit}")
