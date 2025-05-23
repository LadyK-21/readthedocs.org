# Generated by Django 4.2.13 on 2024-06-10 10:29

from django.db import migrations
from django.db import models
from django_safemigrate import Safe


class Migration(migrations.Migration):
    safe = Safe.before_deploy()
    dependencies = [
        ("projects", "0122_add_httpheader_option"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicalproject",
            name="repo_type",
            field=models.CharField(
                choices=[("git", "Git")],
                default="git",
                max_length=10,
                verbose_name="Repository type",
            ),
        ),
        migrations.AlterField(
            model_name="project",
            name="repo_type",
            field=models.CharField(
                choices=[("git", "Git")],
                default="git",
                max_length=10,
                verbose_name="Repository type",
            ),
        ),
    ]
