from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0002_transaction_discount"),
    ]

    operations = [
        migrations.CreateModel(
            name="ManualDebt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("debtor_name", models.CharField(max_length=160)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("debt_date", models.DateField(default=django.utils.timezone.localdate)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("reason", models.CharField(max_length=255)),
                ("notes", models.TextField(blank=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="manual_debts_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="manual_debts",
                        to="business.customer",
                    ),
                ),
            ],
            options={
                "ordering": ["-debt_date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ManualDebtPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("notes", models.CharField(blank=True, max_length=255)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="manual_debt_payments",
                        to="business.moneyaccount",
                    ),
                ),
                (
                    "debt",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="business.manualdebt",
                    ),
                ),
                (
                    "received_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="manual_debt_payments_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
