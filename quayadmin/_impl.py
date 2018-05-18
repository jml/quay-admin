import argparse
import json
import os
import sys

# We need to make sure we know where our SSL certificates are.
# See https://stackoverflow.com/questions/34358935/python-treq-fails-with-twisted-openssl-error-due-to-empty-trust-store-on-windows
import certifi
os.environ["SSL_CERT_FILE"] = certifi.where()

import attr
import treq
from twisted.internet.defer import gatherResults, inlineCallbacks


QUAY_IO_ENDPOINT = 'https://quay.io/api/v1'
QUAY_TOKEN_ENV_NAME = 'QUAY_TOKEN'


@attr.s(frozen=True)
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
        return [Repository(**repo) for repo in repos['repositories']]

    @inlineCallbacks
    def get_user_permissions(self, repo_spec):
        """Get the user permissions for a repository."""
        path = 'repository/%s/permissions/user/' % (repo_spec,)
        perms = yield self._request('GET', path)
        return map(UserPermission.from_dict, perms['permissions'].values())

    @inlineCallbacks
    def get_team_permissions(self, repo_spec):
        path = 'repository/%s/permissions/team/' % (repo_spec,)
        perms = yield self._request('GET', path)
        return map(TeamPermission.from_dict, perms['permissions'].values())


@attr.s(frozen=True, cmp=True)
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

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


@inlineCallbacks
def get_repository_permissions(repository, registry):
    """Get the user and team permissions for a repository.

    Returns a Deferred RepositoryPermissions.
    """
    [user_perms, team_perms] = yield gatherResults([
        registry.get_user_permissions(repository.spec),
        registry.get_team_permissions(repository.spec),
    ])
    return RepositoryPermissions(
        repository=repository,
        user_permissions=user_perms,
        team_permissions=team_perms,
    )


@attr.s(frozen=True)
class Avatar(object):
    color = attr.ib()
    hash = attr.ib()
    kind = attr.ib()
    name = attr.ib()


@attr.s(frozen=True)
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


@attr.s(frozen=True)
class UserPermission(Permission):
    """A permission a user has."""
    is_org_member = attr.ib()
    is_robot = attr.ib()


@attr.s(frozen=True)
class TeamPermission(Permission):
    """A permission a team has."""


@attr.s(frozen=True)
class RepositoryPermissions(object):
    """The permissions for a repository."""

    repository = attr.ib()
    user_permissions = attr.ib()
    team_permissions = attr.ib()

    @classmethod
    def from_dict(cls, data):
        return cls(
            repository=Repository.from_dict(data['repository']),
            user_permissions=map(UserPermission.from_dict, data['user_permissions']),
            team_permissions=map(TeamPermission.from_dict, data['team_permissions']),
        )


@attr.s(frozen=True)
class AllRepositoryPermissions(object):

    _repository_permissions = attr.ib()

    @classmethod
    @inlineCallbacks
    def from_registry(cls, registry, namespace):
        repos = yield registry.list_repositories(namespace)
        perms = yield map_concurrently(get_repository_permissions, repos, registry)
        return cls(perms)

    @classmethod
    def from_json_file(cls, state_file_path):
        with open(state_file_path, 'r') as state_file:
            raw_perms = json.load(state_file)
        return cls([RepositoryPermissions.from_dict(perm) for perm in raw_perms])

    def to_json_file(self, state_file_path):
        with open(state_file_path, 'w') as state_file:
            json.dump([attr.asdict(perm) for perm in self._repository_permissions], state_file)

    def find_repos_with_external_users(self):
        repos = {}
        for perm in self._repository_permissions:
            external_users = [user for user in perm.user_permissions
                              if not user.is_org_member]
            if external_users:
                repos[perm.repository] = external_users
        return repos


def map_concurrently(f, xs, *args, **kwargs):
    """Run 'f' concurrently over each 'x' in 'xs'.

    Also passes through '*args' and '**kwargs'.

    Assumes 'f' returns Deferred values.
    """
    deferreds = [f(x, *args, **kwargs) for x in xs]
    return gatherResults(deferreds)


def make_argument_parser():
    parser = argparse.ArgumentParser(description='Show information about quay.io permissions')
    parser.add_argument('namespace', type=str, help='Namespace to look in')
    parser.add_argument(
        '--from-state', type=str,
        help='If provided, get quay.io state from a file, rather than an API')
    parser.add_argument(
        '--api-root', type=str,
        default=QUAY_IO_ENDPOINT,
        help='Root of quay.io API. Ignored if --from-state provided.')
    parser.add_argument(
        '--dump-state', type=str,
        help='If provided, dump state to a file. Will overwrite file if it exists.')
    return parser


@inlineCallbacks
def main(reactor, *args):
    parser = make_argument_parser()
    config = parser.parse_args(args)
    if config.from_state:
        perms = AllRepositoryPermissions.from_json_file(config.from_state)
    else:
        quay_token = os.environ.get(QUAY_TOKEN_ENV_NAME, None)
        registry = Registry(endpoint=config.api_root, token=quay_token)
        perms = yield AllRepositoryPermissions.from_registry(registry, config.namespace)

    external = perms.find_repos_with_external_users()
    for repo, users in external.items():
        print(repo.spec)
        for user in users:
            print('- %s [%s]%s' % (
                user.name,
                user.role,
                ' (robot)' if user.is_robot else '',
            ))
        print()

    if config.dump_state:
        perms.to_json_file(config.dump_state)

    if external:
        sys.exit(1)


def script():
    """Command-line script for quay-admin."""
    from twisted.internet.task import react
    react(main, sys.argv[1:])
