from django.contrib.admin import register
from django.contrib.auth.admin import UserAdmin

from users.models import User


@register(User)
class CustomUserAmin(UserAdmin):
    list_display = ("username", "email", "first_name", "last_name")
    list_filter = ("username", "email")
