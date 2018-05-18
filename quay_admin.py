import json
import os
import sys

import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

import attr
import treq
from twisted.internet.defer import gatherResults, inlineCallbacks, returnValue
from twisted.internet.task import react


QUAY_IO_ENDPOINT = 'https://quay.io/api/v1'
QUAY_TOKEN_ENV_NAME = 'QUAY_TOKEN'
STATE_FILE = 'quay.state'


@attr.s
class Registry(object):
    """A quay.io registry."""
    endpoint = attr.ib(default=QUAY_IO_ENDPOINT)
    token = attr.ib(default=None)

    def _request(self, method, path, headers=None, **kwargs):
        url = '%s/%s' % (self.endpoint, path)
        headers = headers if headers else {}
        if self.token:
            headers['Authorization'] = 'Bearer %s' % (self.token,)
        return treq.request(method, url, headers=headers, **kwargs).addCallback(treq.json_content)

    @inlineCallbacks
    def list_repositories(self, namespace):
        """List all the repositories in a given namespace.

        Ignores pagination completely.
        """
        repos = yield self._request(
            'GET', 'repository', params={'namespace': namespace})
        returnValue([Repository(**repo) for repo in repos['repositories']])

    @inlineCallbacks
    def get_user_permissions(self, repo_spec):
        """Get the user permissions for a repository."""
        path = 'repository/%s/permissions/user/' % (repo_spec,)
        perms = yield self._request('GET', path)
        returnValue(
            map(UserPermission.from_dict, perms['permissions'].values()))

    @inlineCallbacks
    def get_team_permissions(self, repo_spec):
        path = 'repository/%s/permissions/team/' % (repo_spec,)
        perms = yield self._request('GET', path)
        returnValue(map(TeamPermission.from_dict, perms['permissions'].values()))


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


@inlineCallbacks
def get_repository_permissions(repository, registry):
    """Get the user and team permissions for a repository.

    Returns a Deferred RepositoryPermissions.
    """
    [user_perms, team_perms] = yield gatherResults([
        registry.get_user_permissions(repository.spec),
        registry.get_team_permissions(repository.spec),
    ])
    returnValue(
        RepositoryPermissions(
            repository=repository,
            user_permissions=user_perms,
            team_permissions=team_perms,
        )
    )


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


@attr.s
class RepositoryPermissions(object):
    """The permissions for a repository."""

    repository = attr.ib()
    user_permissions = attr.ib()
    team_permissions = attr.ib()


def map_concurrently(f, xs, *args, **kwargs):
    """Run 'f' concurrently over each 'x' in 'xs'.

    Also passes through '*args' and '**kwargs'.

    Assumes 'f' returns Deferred values.
    """
    deferreds = [f(x, *args, **kwargs) for x in xs]
    return gatherResults(deferreds)


@inlineCallbacks
def main(reactor, *args):
    quay_token = os.environ.get(QUAY_TOKEN_ENV_NAME, None)
    registry = Registry(endpoint=QUAY_IO_ENDPOINT, token=quay_token)
    namespace = 'weaveworks'
    repos = yield registry.list_repositories(namespace)
    perms = yield map_concurrently(get_repository_permissions, repos, registry)
    with open(STATE_FILE, 'w') as state_file:
        json.dump([attr.asdict(perm) for perm in perms], state_file)
    returnValue(None)


if __name__ == '__main__':
    react(main, sys.argv[1:])
