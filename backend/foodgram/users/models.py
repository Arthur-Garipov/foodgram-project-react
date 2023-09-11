from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import UniqueConstraint
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_not_following_self(value):
    if value.user == value.author:
        raise ValidationError(
            _("Нельзя подписаться на самого себя"),
            code="invalid",
        )


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


class Follow(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="follower",
        validators=[validate_not_following_self],
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="following"
    )

    class Meta:
        verbose_name = "Подписка"
        constraints = [
            UniqueConstraint(fields=["author", "user"], name="unique_follower")
        ]

    def __str__(self):
        return f"Автор: {self.author}, подписчик: {self.user}"
