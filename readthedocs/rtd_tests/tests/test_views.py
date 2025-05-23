import csv
from unittest import mock
from urllib.parse import urlsplit

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_dynamic_fixture import get, new

from readthedocs.builds.constants import EXTERNAL
from readthedocs.builds.models import Build, Version
from readthedocs.core.permissions import AdminPermission
from readthedocs.projects.constants import PUBLIC
from readthedocs.projects.models import Feature, Project
from readthedocs.subscriptions.constants import TYPE_SEARCH_ANALYTICS
from readthedocs.subscriptions.products import RTDProductFeature


class PrivateViewsAreProtectedTests(TestCase):
    fixtures = ["eric", "test_data"]

    def assertRedirectToLogin(self, response):
        self.assertEqual(response.status_code, 302)
        url = response["Location"]
        e_scheme, e_netloc, e_path, e_query, e_fragment = urlsplit(url)
        self.assertEqual(e_path, reverse("account_login"))

    def test_dashboard(self):
        response = self.client.get("/dashboard/")
        self.assertRedirectToLogin(response)

    def test_import_wizard_start(self):
        response = self.client.get("/dashboard/import/")
        self.assertRedirectToLogin(response)

    def test_import_wizard_manual(self):
        response = self.client.get("/dashboard/import/manual/")
        self.assertRedirectToLogin(response)

    def test_edit(self):
        response = self.client.get("/dashboard/pip/edit/")
        self.assertRedirectToLogin(response)

    def test_advanced(self):
        response = self.client.get("/dashboard/pip/advanced/")
        self.assertRedirectToLogin(response)

    def test_version_delete_html(self):
        response = self.client.get("/dashboard/pip/version/0.8.1/delete_html/")
        self.assertRedirectToLogin(response)

    def test_version_detail(self):
        response = self.client.get("/dashboard/pip/version/0.8.1/edit/")
        self.assertRedirectToLogin(response)

    def test_project_delete(self):
        response = self.client.get("/dashboard/pip/delete/")
        self.assertRedirectToLogin(response)

    def test_subprojects_delete(self):
        # This URL doesn't exist anymore, 404
        response = self.client.get(
            "/dashboard/pip/subprojects/delete/a-subproject/",
        )
        self.assertEqual(response.status_code, 404)
        # New URL
        response = self.client.get(
            "/dashboard/pip/subprojects/a-subproject/delete/",
        )
        self.assertRedirectToLogin(response)

    def test_subprojects(self):
        response = self.client.get("/dashboard/pip/subprojects/")
        self.assertRedirectToLogin(response)

    def test_project_users(self):
        response = self.client.get("/dashboard/pip/users/")
        self.assertRedirectToLogin(response)

    def test_project_users_delete(self):
        response = self.client.get("/dashboard/pip/users/delete/")
        self.assertRedirectToLogin(response)

    def test_project_notifications(self):
        response = self.client.get("/dashboard/pip/notifications/")
        self.assertRedirectToLogin(response)

    def test_project_notifications_delete(self):
        response = self.client.get("/dashboard/pip/notifications/delete/")
        self.assertRedirectToLogin(response)

    def test_project_translations(self):
        response = self.client.get("/dashboard/pip/translations/")
        self.assertRedirectToLogin(response)

    def test_project_translations_delete(self):
        response = self.client.get(
            "/dashboard/pip/translations/delete/a-translation/",
        )
        self.assertRedirectToLogin(response)

    def test_project_redirects(self):
        response = self.client.get("/dashboard/pip/redirects/")
        self.assertRedirectToLogin(response)

    def test_project_redirects_delete(self):
        response = self.client.get(
            reverse("projects_redirects_delete", args=["pip", 3])
        )
        self.assertRedirectToLogin(response)


class SubprojectViewTests(TestCase):
    def setUp(self):
        self.user = new(User, username="test")
        self.user.set_password("test")
        self.user.save()

        self.project = get(Project, slug="my-mainproject")
        self.subproject = get(Project, slug="my-subproject")
        self.project.add_subproject(self.subproject)

        self.client.login(username="test", password="test")

    def test_deny_delete_for_non_project_admins(self):
        response = self.client.get(
            "/dashboard/my-mainproject/subprojects/delete/my-subproject/",
        )
        self.assertEqual(response.status_code, 404)

        self.assertTrue(
            self.subproject in [r.child for r in self.project.subprojects.all()],
        )

    def test_admins_can_delete_subprojects(self):
        self.project.users.add(self.user)
        self.subproject.users.add(self.user)

        # URL doesn't exist anymore, 404
        response = self.client.get(
            "/dashboard/my-mainproject/subprojects/delete/my-subproject/",
        )
        self.assertEqual(response.status_code, 404)
        # This URL still doesn't accept GET, 405
        response = self.client.get(
            "/dashboard/my-mainproject/subprojects/my-subproject/delete/",
        )
        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            self.subproject in [r.child for r in self.project.subprojects.all()],
        )
        # Test POST
        response = self.client.post(
            "/dashboard/my-mainproject/subprojects/my-subproject/delete/",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.subproject not in [r.child for r in self.project.subprojects.all()],
        )

    def test_project_admins_can_delete_subprojects_that_they_are_not_admin_of(
        self,
    ):
        self.project.users.add(self.user)
        self.assertFalse(AdminPermission.is_admin(self.user, self.subproject))

        response = self.client.post(
            "/dashboard/my-mainproject/subprojects/my-subproject/delete/",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            self.subproject not in [r.child for r in self.project.subprojects.all()],
        )


@mock.patch("readthedocs.projects.tasks.builds.update_docs_task", mock.MagicMock())
class BuildViewTests(TestCase):
    fixtures = ["eric", "test_data"]

    def setUp(self):
        self.client.login(username="eric", password="test")
        self.pip = Project.objects.get(slug="pip")
        self.pip.privacy_level = PUBLIC
        self.pip.external_builds_privacy_level = PUBLIC
        self.pip.save()
        self.pip.versions.update(privacy_level=PUBLIC)

    def test_build_list_includes_external_versions(self):
        external_version = get(
            Version,
            project=self.pip,
            active=True,
            type=EXTERNAL,
            privacy_level=PUBLIC,
        )
        external_version_build = get(Build, project=self.pip, version=external_version)
        self.pip.privacy_level = PUBLIC
        self.pip.save()
        response = self.client.get(
            reverse("builds_project_list", args=[self.pip.slug]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(external_version_build, response.context["build_qs"])


@override_settings(
    RTD_DEFAULT_FEATURES=dict(
        [RTDProductFeature(type=TYPE_SEARCH_ANALYTICS, value=90).to_item()]
    ),
)
class TestSearchAnalyticsView(TestCase):

    """Tests for search analytics page."""

    fixtures = ["eric", "test_data", "test_search_queries"]

    def setUp(self):
        self.client.login(username="eric", password="test")
        self.pip = Project.objects.get(slug="pip")
        self.version = self.pip.versions.order_by("id").first()
        self.analyics_page = reverse("projects_search_analytics", args=[self.pip.slug])

        test_time = timezone.datetime(2019, 8, 2, 12, 0)
        self.test_time = timezone.make_aware(test_time)

        get(Feature, projects=[self.pip])

    def test_top_queries(self):
        with mock.patch("django.utils.timezone.now") as test_time:
            test_time.return_value = self.test_time

            expected_result = [
                ("hello world", 5, 0),
                ("documentation", 4, 0),
                ("read the docs", 4, 0),
                ("advertising", 3, 0),
                ("elasticsearch", 2, 0),
                ("sphinx", 2, 0),
                ("github", 1, 0),
                ("hello", 1, 0),
                ("search", 1, 0),
            ]

            resp = self.client.get(self.analyics_page)

            self.assertEqual(resp.status_code, 200)
            self.assertEqual(
                expected_result,
                list(resp.context["queries"]),
            )

    def test_query_count_of_1_month(self):
        with mock.patch("django.utils.timezone.now") as test_time:
            test_time.return_value = self.test_time

            expected_result_data = [0] * 12 + [1, 1, 2] + [0] * 13 + [4, 3, 7]
            resp = self.client.get(self.analyics_page, {"version": self.version.slug})

            self.assertEqual(resp.status_code, 200)
            self.assertListEqual(
                expected_result_data,
                resp.context["query_count_of_1_month"]["int_data"],
            )
            self.assertEqual(
                "03 Jul",
                resp.context["query_count_of_1_month"]["labels"][0],
            )
            self.assertEqual(
                "02 Aug",
                resp.context["query_count_of_1_month"]["labels"][-1],
            )
            self.assertEqual(
                len(resp.context["query_count_of_1_month"]["labels"]),
                31,
            )
            self.assertEqual(
                len(resp.context["query_count_of_1_month"]["int_data"]),
                31,
            )

    def test_generated_csv_data(self):
        with mock.patch("django.utils.timezone.now") as test_time:
            test_time.return_value = self.test_time

            resp = self.client.get(
                self.analyics_page, {"version": self.version.slug, "download": "true"}
            )

            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp["Content-Type"], "text/csv")

            # convert streaming data to csv format
            content = b"".join(resp.streaming_content).splitlines()
            content = [line.decode("utf-8") for line in content]
            csv_data = csv.reader(content)
            body = list(csv_data)

            self.assertEqual(len(body), 24)
            self.assertEqual(body[0][0], "Created Date")
            self.assertEqual(body[1][1], "advertising")
            self.assertEqual(body[-1][1], "hello world")
