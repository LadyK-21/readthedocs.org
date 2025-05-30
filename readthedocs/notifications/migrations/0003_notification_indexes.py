# Generated by Django 4.2.9 on 2024-01-23 10:50
from django.db import migrations
from django.db import models
from django_safemigrate import Safe


class Migration(migrations.Migration):
    safe = Safe.after_deploy()
    dependencies = [
        ("notifications", "0002_notification_format_values"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="notification",
            options={},
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=["attached_to_content_type", "attached_to_id"],
                name="notificatio_attache_c6aa1d_idx",
            ),
        ),
    ]
