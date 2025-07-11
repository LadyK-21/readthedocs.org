"""OAuth utility functions."""

import json
import re

import structlog
from allauth.socialaccount.providers.bitbucket_oauth2.provider import BitbucketOAuth2Provider
from django.conf import settings
from requests.exceptions import RequestException

from readthedocs.builds import utils as build_utils
from readthedocs.integrations.models import Integration

from ..constants import BITBUCKET
from ..models import RemoteOrganization
from ..models import RemoteRepository
from ..models import RemoteRepositoryRelation
from .base import SyncServiceError
from .base import UserService


log = structlog.get_logger(__name__)


class BitbucketService(UserService):
    """Provider service for Bitbucket."""

    vcs_provider_slug = BITBUCKET
    allauth_provider = BitbucketOAuth2Provider
    base_api_url = "https://api.bitbucket.org"
    # TODO replace this with a less naive check
    url_pattern = re.compile(r"bitbucket.org")
    https_url_pattern = re.compile(r"^https:\/\/[^@]+@bitbucket.org/")

    def sync_repositories(self):
        """Sync repositories from Bitbucket API."""
        remote_repositories = []

        # Get user repos
        try:
            repos = self.paginate(
                "https://bitbucket.org/api/2.0/repositories/",
                role="member",
            )
            for repo in repos:
                remote_repository = self.create_repository(repo)
                remote_repositories.append(remote_repository)

        except (TypeError, ValueError):
            log.warning("Error syncing Bitbucket repositories")
            raise SyncServiceError(
                SyncServiceError.INVALID_OR_REVOKED_ACCESS_TOKEN.format(
                    provider=self.allauth_provider.name
                )
            )

        # Because privileges aren't returned with repository data, run query
        # again for repositories that user has admin role for, and update
        # existing repositories.
        try:
            resp = self.paginate(
                "https://bitbucket.org/api/2.0/repositories/",
                role="admin",
            )
            admin_repo_relations = RemoteRepositoryRelation.objects.filter(
                user=self.user,
                account=self.account,
                remote_repository__vcs_provider=self.vcs_provider_slug,
                remote_repository__remote_id__in=[r["uuid"] for r in resp],
            )
            for remote_repository_relation in admin_repo_relations:
                remote_repository_relation.admin = True
                remote_repository_relation.save()
        except (TypeError, ValueError):
            pass

        return remote_repositories

    def sync_organizations(self):
        """Sync Bitbucket workspaces(our RemoteOrganization) and workspace repositories."""
        remote_organizations = []
        remote_repositories = []

        try:
            workspaces = self.paginate(
                f"{self.base_api_url}/2.0/workspaces/",
                role="member",
            )
            for workspace in workspaces:
                remote_organization = self.create_organization(workspace)
                repos = self.paginate(workspace["links"]["repositories"]["href"])

                remote_organizations.append(remote_organization)

                for repo in repos:
                    remote_repository = self.create_repository(
                        repo,
                        organization=remote_organization,
                    )
                    remote_repositories.append(remote_repository)

        except ValueError:
            log.warning("Error syncing Bitbucket organizations")
            raise SyncServiceError(
                SyncServiceError.INVALID_OR_REVOKED_ACCESS_TOKEN.format(
                    provider=self.allauth_provider.name
                )
            )

        return remote_organizations, remote_repositories

    def create_repository(self, fields, privacy=None, organization=None):
        """
        Update or create a repository from Bitbucket API response.

        .. note::
            The :py:data:`admin` property is not set during creation, as
            permissions are not part of the returned repository data from
            Bitbucket.

        :param fields: dictionary of response data from API
        :param privacy: privacy level to support
        :param organization: remote organization to associate with
        :type organization: RemoteOrganization
        :rtype: RemoteRepository
        """
        privacy = privacy or settings.DEFAULT_PRIVACY_LEVEL
        if any(
            [
                (privacy == "private"),
                (fields["is_private"] is False and privacy == "public"),
            ]
        ):
            repo, _ = RemoteRepository.objects.get_or_create(
                remote_id=fields["uuid"], vcs_provider=self.vcs_provider_slug
            )
            repo.get_remote_repository_relation(self.user, self.account)

            if repo.organization and repo.organization != organization:
                log.debug(
                    "Not importing repository because mismatched orgs.",
                    repository=fields["name"],
                )
                return None

            repo.organization = organization
            repo.name = fields["name"]
            repo.full_name = fields["full_name"]
            repo.description = fields["description"]
            repo.private = fields["is_private"]

            # Default to HTTPS, use SSH for private repositories
            clone_urls = {u["name"]: u["href"] for u in fields["links"]["clone"]}
            repo.clone_url = self.https_url_pattern.sub(
                "https://bitbucket.org/",
                clone_urls.get("https"),
            )
            repo.ssh_url = clone_urls.get("ssh")
            if repo.private:
                repo.clone_url = repo.ssh_url

            repo.html_url = fields["links"]["html"]["href"]
            repo.vcs = fields["scm"]
            mainbranch = fields.get("mainbranch") or {}
            repo.default_branch = mainbranch.get("name")

            avatar_url = fields["links"]["avatar"]["href"] or ""
            repo.avatar_url = re.sub(r"\/16\/$", r"/32/", avatar_url)
            if not repo.avatar_url:
                repo.avatar_url = self.default_user_avatar_url

            repo.save()

            return repo

        log.debug(
            "Not importing repository because mismatched type.",
            repository=fields["name"],
        )

    def create_organization(self, fields):
        """
        Update or create remote organization from Bitbucket API response.

        :param fields: dictionary response of data from API
        :rtype: RemoteOrganization
        """
        organization, _ = RemoteOrganization.objects.get_or_create(
            remote_id=fields["uuid"], vcs_provider=self.vcs_provider_slug
        )
        organization.get_remote_organization_relation(self.user, self.account)

        organization.slug = fields.get("slug")
        organization.name = fields.get("name")
        organization.url = fields["links"]["html"]["href"]
        organization.avatar_url = fields["links"]["avatar"]["href"]
        if not organization.avatar_url:
            organization.avatar_url = self.default_org_avatar_url

        organization.save()

        return organization

    def get_next_url_to_paginate(self, response):
        return response.json().get("next")

    def get_paginated_results(self, response):
        return response.json().get("values", [])

    def get_webhook_data(self, project, integration):
        """Get webhook JSON data to post to the API."""
        return json.dumps(
            {
                "description": "Read the Docs ({domain})".format(
                    domain=settings.PRODUCTION_DOMAIN,
                ),
                "url": self.get_webhook_url(project, integration),
                "active": True,
                "secret": integration.secret,
                "events": ["repo:push"],
            }
        )

    def get_provider_data(self, project, integration):
        """
        Gets provider data from Bitbucket Webhooks API.

        :param project: project
        :type project: Project
        :param integration: Integration for the project
        :type integration: Integration
        :returns: Dictionary containing provider data from the API or None
        :rtype: dict
        """

        if integration.provider_data:
            return integration.provider_data

        owner, repo = build_utils.get_bitbucket_username_repo(url=project.repo)
        url = f"{self.base_api_url}/2.0/repositories/{owner}/{repo}/hooks"

        rtd_webhook_url = self.get_webhook_url(project, integration)

        structlog.contextvars.bind_contextvars(
            project_slug=project.slug,
            integration_id=integration.pk,
            url=url,
        )
        try:
            resp = self.session.get(url)

            if resp.status_code == 200:
                recv_data = resp.json()

                for webhook_data in recv_data["values"]:
                    if webhook_data["url"] == rtd_webhook_url:
                        integration.provider_data = webhook_data
                        integration.save()

                        log.info(
                            "Bitbucket integration updated with provider data for project.",
                        )
                        break
            else:
                log.info(
                    "Bitbucket project does not exist or user does not have permissions.",
                )

        except Exception:
            log.exception(
                "Bitbucket webhook Listing failed for project.",
            )

        return integration.provider_data

    def setup_webhook(self, project, integration=None) -> bool:
        """
        Set up Bitbucket project webhook for project.

        :param project: project to set up webhook for
        :type project: Project
        :param integration: Integration for the project
        :type integration: Integration
        :returns: boolean based on webhook set up success, and requests Response object
        """
        owner, repo = build_utils.get_bitbucket_username_repo(url=project.repo)
        url = f"{self.base_api_url}/2.0/repositories/{owner}/{repo}/hooks"
        if not integration:
            integration, _ = Integration.objects.get_or_create(
                project=project,
                integration_type=Integration.BITBUCKET_WEBHOOK,
            )

        data = self.get_webhook_data(project, integration)
        resp = None
        structlog.contextvars.bind_contextvars(
            project_slug=project.slug,
            integration_id=integration.pk,
            url=url,
        )

        try:
            resp = self.session.post(
                url,
                data=data,
                headers={"content-type": "application/json"},
            )
            if resp.status_code == 201:
                recv_data = resp.json()
                integration.provider_data = recv_data
                integration.save()
                log.debug(
                    "Bitbucket webhook creation successful for project.",
                )
                return True

            if resp.status_code in [401, 403, 404]:
                log.info(
                    "Bitbucket project does not exist or user does not have permissions.",
                )
            else:
                try:
                    debug_data = resp.json()
                except ValueError:
                    debug_data = resp.content
                log.warning(
                    "Bitbucket webhook creation failed.",
                    debug_data=debug_data,
                )

        # Catch exceptions with request or deserializing JSON
        except (RequestException, ValueError):
            log.exception("Bitbucket webhook creation failed for project.")

        return False

    def update_webhook(self, project, integration) -> bool:
        """
        Update webhook integration.

        :param project: project to set up webhook for
        :type project: Project
        :param integration: Webhook integration to update
        :type integration: Integration
        :returns: boolean based on webhook set up success, and requests Response object
        """
        structlog.contextvars.bind_contextvars(project_slug=project.slug)
        provider_data = self.get_provider_data(project, integration)

        # Handle the case where we don't have a proper provider_data set
        # This happens with a user-managed webhook previously
        if not provider_data:
            return self.setup_webhook(project, integration)

        data = self.get_webhook_data(project, integration)
        resp = None
        try:
            # Expect to throw KeyError here if provider_data is invalid
            url = provider_data["links"]["self"]["href"]
            resp = self.session.put(
                url,
                data=data,
                headers={"content-type": "application/json"},
            )

            if resp.status_code == 200:
                recv_data = resp.json()
                integration.provider_data = recv_data
                integration.save()
                log.info("Bitbucket webhook update successful for project.")
                return True

            # Bitbucket returns 404 when the webhook doesn't exist. In this
            # case, we call ``setup_webhook`` to re-configure it from scratch
            if resp.status_code == 404:
                return self.setup_webhook(project, integration)

            # Response data should always be JSON, still try to log if not though
            try:
                debug_data = resp.json()
            except ValueError:
                debug_data = resp.content
            log.error(
                "Bitbucket webhook update failed.",
                debug_data=debug_data,
            )

        # Catch exceptions with request or deserializing JSON
        except (KeyError, RequestException, TypeError, ValueError):
            log.exception("Bitbucket webhook update failed for project.")

        return False
