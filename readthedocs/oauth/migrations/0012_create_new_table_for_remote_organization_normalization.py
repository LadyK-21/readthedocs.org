import django.db.models.deletion
import django_extensions.db.fields

# Generated by Django 2.2.17 on 2020-12-23 10:58
from django.conf import settings
from django.db import migrations
from django.db import models
from django_safemigrate import Safe


class Migration(migrations.Migration):
    safe = Safe.after_deploy()
    dependencies = [
        ("socialaccount", "0003_extra_data_default_dict"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("oauth", "0011_add_default_branch"),
    ]

    operations = [
        migrations.CreateModel(
            name="RemoteOrganization",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("slug", models.CharField(max_length=255, verbose_name="Slug")),
                (
                    "name",
                    models.CharField(blank=True, max_length=255, null=True, verbose_name="Name"),
                ),
                (
                    "email",
                    models.EmailField(blank=True, max_length=255, null=True, verbose_name="Email"),
                ),
                (
                    "avatar_url",
                    models.URLField(blank=True, null=True, verbose_name="Avatar image URL"),
                ),
                (
                    "url",
                    models.URLField(blank=True, null=True, verbose_name="URL to organization page"),
                ),
                ("remote_id", models.CharField(db_index=True, max_length=128)),
                (
                    "vcs_provider",
                    models.CharField(
                        choices=[
                            ("github", "GitHub"),
                            ("gitlab", "GitLab"),
                            ("bitbucket", "Bitbucket"),
                        ],
                        max_length=32,
                        verbose_name="VCS provider",
                    ),
                ),
            ],
            options={
                "db_table": "oauth_remoteorganization_2020",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="RemoteOrganizationRelation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="remote_organization_relations",
                        to="socialaccount.SocialAccount",
                        verbose_name="Connected account",
                    ),
                ),
                (
                    "remote_organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="remote_organization_relations",
                        to="oauth.RemoteOrganization",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="remote_organization_relations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "unique_together": {("remote_organization", "account")},
            },
        ),
        migrations.AddField(
            model_name="remoteorganization",
            name="users",
            field=models.ManyToManyField(
                related_name="oauth_organizations",
                through="oauth.RemoteOrganizationRelation",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Users",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="remoteorganization",
            unique_together={("remote_id", "vcs_provider")},
        ),
    ]
