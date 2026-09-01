from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CASHIER = "cashier", "Cashier"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CASHIER)
    avatar = models.FileField(
        upload_to="users/avatars/",
        blank=True,
        validators=[FileExtensionValidator(["png", "jpg", "jpeg", "webp"])],
    )

    def is_company_admin(self):
        return self.is_superuser or self.role == self.Role.ADMIN

    @property
    def display_name(self):
        return self.get_full_name().strip() or self.username
