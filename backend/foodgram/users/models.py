from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(
        verbose_name="Электронная почта", unique=True, max_length=254
    )
    first_name = models.CharField(
        verbose_name="Имя",
        max_length=150,
    )
    last_name = models.CharField(
        verbose_name="Фамилия",
        max_length=150,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ("username", "first_name", "last_name")

    class Meta:
        verbose_name = "Пользователь"
        constraints = [
            models.UniqueConstraint(
                fields=("username", "email"), name="unique_user"
            )
        ]

    def __str__(self):
        return self.username
