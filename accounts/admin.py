from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Company role", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Company role", {"fields": ("role",)}),)
    list_display = ("username", "first_name", "last_name", "role", "is_active", "is_staff")
