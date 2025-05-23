# Generated by Django 2.2.10 on 2020-02-25 23:59
import autoslug.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations
from django.db import models
from django_safemigrate import Safe


class Migration(migrations.Migration):
    safe = Safe.after_deploy()
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0002_add_importedfile_model"),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
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
                    "pub_date",
                    models.DateTimeField(auto_now_add=True, verbose_name="Publication date"),
                ),
                (
                    "modified_date",
                    models.DateTimeField(auto_now=True, verbose_name="Modified date"),
                ),
                ("name", models.CharField(max_length=100, verbose_name="Name")),
                (
                    "slug",
                    models.SlugField(max_length=255, unique=True, verbose_name="Slug"),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True,
                        help_text=b"How can we get in touch with you?",
                        max_length=255,
                        null=True,
                        verbose_name="E-mail",
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text=b"Tell us a little about yourself.",
                        null=True,
                        verbose_name="Description",
                    ),
                ),
                (
                    "url",
                    models.URLField(
                        blank=True,
                        help_text=b"The main website for your Organization",
                        max_length=255,
                        null=True,
                        verbose_name="Home Page",
                    ),
                ),
                (
                    "public_key",
                    models.TextField(
                        blank=True,
                        help_text=b"Add this to your version control to give us access. Specific to your Organization.",
                        null=True,
                        verbose_name="Public SSH Key",
                    ),
                ),
                (
                    "private_key",
                    models.TextField(blank=True, null=True, verbose_name="Private SSH Key"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OrganizationOwner",
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
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="organizations.Organization",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Team",
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
                    "pub_date",
                    models.DateTimeField(auto_now_add=True, verbose_name="Publication date"),
                ),
                (
                    "modified_date",
                    models.DateTimeField(auto_now=True, verbose_name="Modified date"),
                ),
                ("name", models.CharField(max_length=100, verbose_name="Name")),
                ("slug", models.SlugField(max_length=255, verbose_name="Slug")),
                (
                    "access",
                    models.CharField(
                        choices=[(b"readonly", "Read-only"), (b"admin", "Admin")],
                        default=b"readonly",
                        max_length=100,
                        verbose_name="Access",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TeamInvite",
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
                    "pub_date",
                    models.DateTimeField(auto_now_add=True, verbose_name="Publication date"),
                ),
                (
                    "modified_date",
                    models.DateTimeField(auto_now=True, verbose_name="Modified date"),
                ),
                ("email", models.EmailField(max_length=254, verbose_name="E-mail")),
                ("hash", models.CharField(max_length=250, verbose_name="Hash")),
                ("count", models.IntegerField(default=0, verbose_name="Count")),
                ("total", models.IntegerField(default=10, verbose_name="Total")),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites",
                        to="organizations.Organization",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites",
                        to="organizations.Team",
                        verbose_name="Team",
                    ),
                ),
            ],
            options={
                "unique_together": {("team", "email")},
            },
        ),
        migrations.CreateModel(
            name="TeamMember",
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
                    "invite",
                    models.ForeignKey(
                        blank=True,
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="organizations.TeamInvite",
                    ),
                ),
                (
                    "member",
                    models.ForeignKey(
                        blank=True,
                        default=None,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="organizations.Team",
                    ),
                ),
            ],
            options={
                "unique_together": {
                    ("team", "member"),
                    ("team", "invite"),
                    ("team", "member", "invite"),
                },
            },
        ),
        migrations.AddField(
            model_name="team",
            name="members",
            field=models.ManyToManyField(
                blank=True,
                related_name="teams",
                through="organizations.TeamMember",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Users",
            ),
        ),
        migrations.AddField(
            model_name="team",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="teams",
                to="organizations.Organization",
            ),
        ),
        migrations.AddField(
            model_name="team",
            name="projects",
            field=models.ManyToManyField(
                blank=True,
                related_name="teams",
                to="projects.Project",
                verbose_name="Projects",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="owners",
            field=models.ManyToManyField(
                related_name="owner_organizations",
                through="organizations.OrganizationOwner",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Owners",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="projects",
            field=models.ManyToManyField(
                related_name="organizations",
                to="projects.Project",
                verbose_name="Projects",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="team",
            unique_together={("name", "organization"), ("slug", "organization")},
        ),
        migrations.AddField(
            model_name="organization",
            name="stripe_id",
            field=models.CharField(
                blank=True, max_length=100, null=True, verbose_name="Stripe customer ID"
            ),
        ),
        migrations.AlterField(
            model_name="team",
            name="slug",
            field=autoslug.fields.AutoSlugField(
                always_update=True,
                editable=False,
                populate_from=models.CharField(max_length=100, verbose_name="Name"),
                unique_with=[b"organization"],
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="disabled",
            field=models.BooleanField(
                default=False,
                help_text="Docs and builds are disabled for this organization",
                verbose_name="Disabled",
            ),
        ),
        migrations.AlterModelOptions(
            name="organization",
            options={"get_latest_by": ["-pub_date"], "ordering": ["name"]},
        ),
        migrations.AlterField(
            model_name="organization",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Tell us a little about yourself.",
                null=True,
                verbose_name="Description",
            ),
        ),
        migrations.AlterField(
            model_name="organization",
            name="email",
            field=models.EmailField(
                blank=True,
                help_text="How can we get in touch with you?",
                max_length=255,
                null=True,
                verbose_name="E-mail",
            ),
        ),
        migrations.RemoveField(
            model_name="organization",
            name="public_key",
        ),
        migrations.AlterField(
            model_name="organization",
            name="url",
            field=models.URLField(
                blank=True,
                help_text="The main website for your Organization",
                max_length=255,
                null=True,
                verbose_name="Home Page",
            ),
        ),
        migrations.AlterField(
            model_name="team",
            name="access",
            field=models.CharField(
                choices=[("readonly", "Read-only"), ("admin", "Admin")],
                default="readonly",
                max_length=100,
                verbose_name="Access",
            ),
        ),
        migrations.AlterField(
            model_name="team",
            name="slug",
            field=autoslug.fields.AutoSlugField(
                always_update=True,
                editable=False,
                populate_from="name",
                unique_with=["organization"],
            ),
        ),
        migrations.RemoveField(
            model_name="organization",
            name="private_key",
        ),
    ]
