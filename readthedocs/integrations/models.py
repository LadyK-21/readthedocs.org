"""Integration models for external services."""

import json
import re
import uuid
from dataclasses import dataclass

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db import transaction
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer
from rest_framework import status

from readthedocs.core.fields import default_token
from readthedocs.projects.models import Project

from .utils import normalize_request_payload


class HttpExchangeManager(models.Manager):
    """HTTP exchange manager methods."""

    # Filter rules for request headers to remove from the output
    REQ_FILTER_RULES = [
        re.compile("^X-Forwarded-.*$", re.I),
        re.compile("^X-Real-Ip$", re.I),
    ]

    @transaction.atomic
    def from_exchange(self, req, resp, related_object, payload=None):
        """
        Create object from Django request and response objects.

        If an explicit Request ``payload`` is not specified, the payload will be
        determined directly from the Request object. This makes a good effort to
        normalize the data, however we don't enforce that the payload is JSON

        :param req: Request object to store
        :type req: HttpRequest
        :param resp: Response object to store
        :type resp: HttpResponse
        :param related_object: Object to use for generic relation
        :param payload: Alternate payload object to store
        :type payload: dict
        """
        request_payload = payload
        if request_payload is None:
            request_payload = normalize_request_payload(req)
        try:
            request_body = json.dumps(request_payload, sort_keys=True)
        except TypeError:
            request_body = str(request_payload)
        # This is the rawest form of request header we have, the WSGI
        # headers. HTTP headers are prefixed with `HTTP_`, which we remove,
        # and because the keys are all uppercase, we'll normalize them to
        # title case-y hyphen separated values.
        request_headers = {
            key[5:].title().replace("_", "-"): str(val)
            for (key, val) in list(req.META.items())
            if key.startswith("HTTP_")
        }  # yapf: disable

        request_headers["Content-Type"] = req.content_type
        # Remove unwanted headers
        for filter_rule in self.REQ_FILTER_RULES:
            for key in list(request_headers.keys()):
                if filter_rule.match(key):
                    del request_headers[key]

        response_payload = resp.data if hasattr(resp, "data") else resp.content
        try:
            response_body = json.dumps(response_payload, sort_keys=True)
        except TypeError:
            response_body = str(response_payload)
        response_headers = dict(list(resp.items()))

        fields = {
            "status_code": resp.status_code,
            "request_headers": request_headers,
            "request_body": request_body,
            "response_body": response_body,
            "response_headers": response_headers,
        }
        fields["related_object"] = related_object
        obj = self.create(**fields)
        self.delete_limit(related_object)
        return obj

    def from_requests_exchange(self, response, related_object):
        """
        Create an exchange object from a requests' response.

        :param response: The result from calling request.post() or similar.
        :param related_object: Object to use for generic relationship.
        """
        request = response.request
        # NOTE: we need to cast ``request.headers`` and ``response.headers``
        # because it's a ``requests.structures.CaseInsensitiveDict`` which is
        # not JSON serializable.
        obj = self.create(
            related_object=related_object,
            request_headers=dict(request.headers) or {},
            request_body=request.body or "",
            status_code=response.status_code,
            response_headers=dict(response.headers),
            response_body=response.text,
        )
        self.delete_limit(related_object)
        return obj

    def delete_limit(self, related_object, limit=10):
        # If the related_object is an instance of Integration,
        # it could be a proxy model, so we force it to always be the "real" model.
        if isinstance(related_object, Integration):
            model = Integration
        else:
            model = related_object

        queryset = self.filter(
            content_type=ContentType.objects.get(
                app_label=model._meta.app_label,
                model=model._meta.model_name,
            ),
            object_id=related_object.pk,
        )
        for exchange in queryset[limit:]:
            exchange.delete()


class HttpExchange(models.Model):
    """HTTP request/response exchange."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    related_object = GenericForeignKey("content_type", "object_id")

    date = models.DateTimeField(_("Date"), auto_now_add=True)

    request_headers = models.JSONField(
        _("Request headers"),
        # Delete after deploy
        null=True,
        blank=True,
    )
    request_body = models.TextField(_("Request body"))

    response_headers = models.JSONField(
        _("Request headers"),
        # Delete after deploy
        null=True,
        blank=True,
    )
    response_body = models.TextField(_("Response body"))

    status_code = models.IntegerField(
        _("Status code"),
        default=status.HTTP_200_OK,
    )

    objects = HttpExchangeManager()

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["content_type", "object_id", "date"])]

    def __str__(self):
        return _("Exchange {0}").format(self.pk)

    @property
    def failed(self):
        # Assume anything that isn't 2xx level status code is an error
        return not (200 <= self.status_code < 300)

    def formatted_json(self, field):
        """Try to return pretty printed and Pygment highlighted code."""
        value = getattr(self, field) or ""
        try:
            if not isinstance(value, dict):
                value = json.loads(value)
            json_value = json.dumps(value, sort_keys=True, indent=2)
            formatter = HtmlFormatter()
            html = highlight(json_value, JsonLexer(), formatter)
            return mark_safe(html)
        except (ValueError, TypeError):
            return value

    @property
    def formatted_request_body(self):
        return self.formatted_json("request_body")

    @property
    def formatted_response_body(self):
        return self.formatted_json("response_body")


class IntegrationQuerySet(models.QuerySet):
    """
    Return a subclass of Integration, based on the integration type.

    .. note::

        This doesn't affect queries currently, only fetching of an object
    """

    def _get_subclass(self, integration_type):
        # Build a mapping of integration_type -> class dynamically
        class_map = {
            cls.integration_type_id: cls
            for cls in self.model.__subclasses__()
            if hasattr(cls, "integration_type_id")
        }  # yapf: disable
        return class_map.get(integration_type)

    def _get_subclass_replacement(self, original):
        """
        Replace model instance on Integration subclasses.

        This is based on the ``integration_type`` field, and is used to provide
        specific functionality to and integration via a proxy subclass of the
        Integration model.
        """
        cls_replace = self._get_subclass(original.integration_type)
        if cls_replace is None:
            return original
        new = cls_replace()
        for k, v in list(original.__dict__.items()):
            new.__dict__[k] = v
        return new

    def get(self, *args, **kwargs):
        original = super().get(*args, **kwargs)
        return self._get_subclass_replacement(original)

    def subclass(self, instance=None):
        """
        Return a subclass or list of subclasses integrations.

        If an instance was passed in, return a single subclasses integration
        instance. If this is a queryset or manager, render the list as a list
        using the integration subsclasses.
        """
        if instance is None:
            return [self._get_subclass_replacement(_instance) for _instance in self]
        return self._get_subclass_replacement(instance)

    def create(self, **kwargs):
        """
        Override of create method to use subclass instance instead.

        Instead of using the underlying Integration model to create this
        instance, we get the correct subclass to use instead. This allows for
        overrides to ``save`` and other model functions on object creation.
        """
        model_cls = self._get_subclass(kwargs.get("integration_type"))
        if model_cls is None:
            model_cls = self.model
        obj = model_cls(**kwargs)
        self._for_write = True
        obj.save(force_insert=True, using=self.db)
        return obj


class Integration(TimeStampedModel):
    """Inbound webhook integration for projects."""

    GITHUBAPP = "githubapp"
    GITHUB_WEBHOOK = "github_webhook"
    BITBUCKET_WEBHOOK = "bitbucket_webhook"
    GITLAB_WEBHOOK = "gitlab_webhook"
    API_WEBHOOK = "api_webhook"

    WEBHOOK_INTEGRATIONS = (
        (GITHUB_WEBHOOK, _("GitHub incoming webhook")),
        (BITBUCKET_WEBHOOK, _("Bitbucket incoming webhook")),
        (GITLAB_WEBHOOK, _("GitLab incoming webhook")),
        (API_WEBHOOK, _("Generic API incoming webhook")),
    )

    REMOTE_ONLY_INTEGRATIONS = ((GITHUBAPP, _("GitHub App")),)

    INTEGRATIONS = WEBHOOK_INTEGRATIONS + REMOTE_ONLY_INTEGRATIONS

    project = models.ForeignKey(
        Project,
        related_name="integrations",
        on_delete=models.CASCADE,
    )
    integration_type = models.CharField(
        _("Integration type"),
        max_length=32,
        choices=INTEGRATIONS,
    )
    provider_data = models.JSONField(
        _("Provider data"),
        null=True,
        blank=True,
    )
    exchanges = GenericRelation(
        "HttpExchange",
        related_query_name="integrations",
    )
    secret = models.CharField(
        help_text=_("Secret used to validate the payload of the webhook"),
        max_length=255,
        blank=True,
        null=True,
    )

    objects = IntegrationQuerySet.as_manager()

    # Integration attributes
    has_sync = False
    is_remote_only = False
    is_active = True

    def __str__(self):
        return self.get_integration_type_display()

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = get_random_string(length=32)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("projects_integrations_detail", args=(self.project.slug, self.pk))


class GitHubWebhook(Integration):
    integration_type_id = Integration.GITHUB_WEBHOOK
    has_sync = True

    class Meta:
        proxy = True

    @property
    def can_sync(self):
        try:
            return all((k in self.provider_data) for k in ["id", "url"])
        except (ValueError, TypeError):
            return False


@dataclass
class GitHubAppIntegrationProviderData:
    installation_id: int
    repository_id: int
    repository_full_name: str


class GitHubAppIntegration(Integration):
    """
    Dummy integration for GitHub App projects.

    This is a proxy model for the Integration model, which is used to
    represent GitHub App integrations in the UI.

    This integration is automatically created when a project is linked to a
    remote repository from a GitHub App installation, and it remains
    associated with the project even if the remote repository is removed.

    The `provider_data` field is a JSON representation of the `GitHubAppIntegrationProviderData` class.
    """

    integration_type_id = Integration.GITHUBAPP
    has_sync = False
    is_remote_only = True

    class Meta:
        proxy = True

    def get_absolute_url(self) -> str | None:
        """
        Get URL of the GHA installation page.

        Instead of showing a link to the integration details page, for GHA
        projects we show a link in the UI to the GHA installation page for the
        installation used by the project.
        """
        # If the GHA is disconnected we'll disonnect the remote repository and
        # so we won't have a URL to the installation page the project should be
        # using. We might want to store this on the model later so a repository
        # that is removed from the installation can still link to the
        # installation the project was _previously_ using.
        if self.project.is_github_app_project:
            return self.project.remote_repository.github_app_installation.url
        return None

    @property
    def is_active(self) -> bool:
        """
        Is the GHA connection active for this project?

        This assumes that the status of the GHA connect will be reflected as
        soon as there is an event that might disconnect the GHA on GitHub's
        side -- uninstalling the app or revoking permission to the repository.
        We listen for these events and should disconnect the remote
        repository, but would leave this integration.
        """
        return self.project.is_github_app_project


class BitbucketWebhook(Integration):
    integration_type_id = Integration.BITBUCKET_WEBHOOK
    has_sync = True

    class Meta:
        proxy = True

    @property
    def can_sync(self):
        try:
            return all((k in self.provider_data) for k in ["uuid", "url"])
        except (ValueError, TypeError):
            return False


class GitLabWebhook(Integration):
    integration_type_id = Integration.GITLAB_WEBHOOK
    has_sync = True

    class Meta:
        proxy = True

    @property
    def can_sync(self):
        try:
            return all((k in self.provider_data) for k in ["id", "url"])
        except (ValueError, TypeError):
            return False


class GenericAPIWebhook(Integration):
    integration_type_id = Integration.API_WEBHOOK
    has_sync = False

    class Meta:
        proxy = True

    def save(self, *args, **kwargs):
        """Ensure model has token data before saving."""
        try:
            token = self.provider_data.get("token")
        except (AttributeError, TypeError):
            token = None
        finally:
            if token is None:
                token = default_token()
                self.provider_data = {"token": token}
        super().save(*args, **kwargs)

    @property
    def token(self):
        """Get or generate a secret token for authentication."""
        return self.provider_data.get("token")
