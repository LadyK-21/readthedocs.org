# Generated by Django 3.2.13 on 2022-08-03 18:25
from django.db import migrations
from django.utils import timezone
from django_safemigrate import Safe


def forwards_func(apps, schema_editor):
    """Migrate the new null fields from the Domain model."""
    Domain = apps.get_model("projects", "Domain")
    Domain.objects.filter(skip_validation=None).update(skip_validation=False)
    Domain.objects.filter(validation_process_start=None).update(
        validation_process_start=timezone.now()
    )


class Migration(migrations.Migration):
    safe = Safe.after_deploy
    dependencies = [
        ("projects", "0092_add_new_fields"),
    ]

    operations = [
        migrations.RunPython(forwards_func),
    ]
