import os
from pprint import pprint
import time

import attr
import requests


QUAY_IO_ENDPOINT = 'https://quay.io/api/v1'
QUAY_TOKEN_ENV_NAME = 'QUAY_TOKEN'


@attr.s
class BearerToken(requests.auth.AuthBase):
    """Bearer token authorization."""
    token = attr.ib()

    def __call__(self, r):
        r.headers['Authorization'] = 'Bearer %s' % (self.token,)
        return r


@attr.s
class Registry(object):
    """A quay.io registry."""
    endpoint = attr.ib(default=QUAY_IO_ENDPOINT)
    auth = attr.ib(default=None)

    def list_repositories(self, namespace):
        """List all the repositories in a given namespace.

        Ignores pagination completely.
        """
        url = '%s/repository' % self.endpoint
        repos = requests.get(
            url, params={'namespace': namespace}, auth=self.auth).json()
        return [Repository(**repo) for repo in repos['repositories']]

    def get_user_permissions(self, repo_spec):
        """Get the user permissions for a repository."""
        url = '%s/repository/%s/permissions/user/' % (self.endpoint, repo_spec)
        perms = requests.get(url, auth=self.auth).json()
        return map(UserPermission.from_dict, perms['permissions'].values())

    def get_team_permissions(self, repo_spec):
        url = '%s/repository/%s/permissions/team/' % (self.endpoint, repo_spec)
        perms = requests.get(url, auth=self.auth).json()
        return map(TeamPermission.from_dict, perms['permissions'].values())


@attr.s
class Repository(object):
    """A quay.io repository."""

    namespace = attr.ib()
    name = attr.ib()
    kind = attr.ib()
    is_starred = attr.ib()
    is_public = attr.ib()
    description = attr.ib()

    @property
    def spec(self):
        return '%s/%s' % (self.namespace, self.name)


@attr.s
class Avatar(object):
    color = attr.ib()
    hash = attr.ib()
    kind = attr.ib()
    name = attr.ib()


@attr.s
class Permission(object):
    """Base permission class."""
    avatar = attr.ib()
    name = attr.ib()
    role = attr.ib()

    @classmethod
    def from_dict(cls, data):
        avatar_data = data.pop('avatar')
        avatar = Avatar(**avatar_data)
        return cls(avatar=avatar, **data)


@attr.s
class UserPermission(Permission):
    """A permission a user has."""
    is_org_member = attr.ib()
    is_robot = attr.ib()


@attr.s
class TeamPermission(Permission):
    """A permission a team has."""


def main():
    quay_token = os.environ.get(QUAY_TOKEN_ENV_NAME, None)
    auth = BearerToken(token=quay_token) if quay_token else None
    registry = Registry(auth=auth)
    repos = registry.list_repositories('weaveworks')
    for repo in repos:
        user_perms = registry.get_user_permissions(repo.spec)
        team_perms = registry.get_team_permissions(repo.spec)
        print repo
        pprint(user_perms)
        pprint(team_perms)
        time.sleep(2)


if __name__ == '__main__':
    main()
