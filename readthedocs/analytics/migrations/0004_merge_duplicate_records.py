# Generated by Django 3.2.13 on 2022-07-06 21:11
from django.db import migrations
from django.db.models import Count
from django_safemigrate import Safe


def forwards_func(apps, schema_editor):
    """Merge records with duplicated entries."""
    PageView = apps.get_model("analytics", "PageView")
    queryset = (
        PageView.objects.filter(version=None)
        .values("project", "date", "path", "status")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )
    for result in queryset:
        count = result.pop("count")
        duplicates = list(
            PageView.objects.filter(
                **result,
                version=None,
            )
        )
        if duplicates:
            pageview = duplicates[0]
            pageview.view_count = count
            pageview.save()
            PageView.objects.filter(id__in=[pv.id for pv in duplicates[1:]]).delete()


class Migration(migrations.Migration):
    safe = Safe.after_deploy()
    dependencies = [
        ("analytics", "0003_remove_index"),
    ]

    operations = [
        migrations.RunPython(forwards_func),
    ]
