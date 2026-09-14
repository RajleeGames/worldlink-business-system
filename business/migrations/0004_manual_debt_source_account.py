from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("business", "0003_manual_debt"),
    ]

    operations = [
        migrations.AddField(
            model_name="manualdebt",
            name="source_account",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="manual_debts_given",
                to="business.moneyaccount",
            ),
        ),
        migrations.AddField(
            model_name="manualdebt",
            name="disbursement_reference",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
