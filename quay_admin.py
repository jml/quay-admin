import os
from pprint import pprint

import attr
import requests


QUAY_IO_ENDPOINT = 'https://quay.io/api/v1'
QUAY_TOKEN_ENV_NAME = 'QUAY_TOKEN'


@attr.s
class BearerToken(requests.auth.AuthBase):
    token = attr.ib()

    def __call__(self, r):
        r.headers['Authorization'] = 'Bearer %s' % (self.token,)
        return r


@attr.s
class Registry(object):
    endpoint = attr.ib(default=QUAY_IO_ENDPOINT)
    auth = attr.ib(default=None)

    def list_repositories(self, namespace):
        url = '%s/repository' % self.endpoint
        return requests.get(
            url, params={'namespace': namespace}, auth=self.auth).json()


def main():
    quay_token = os.environ.get(QUAY_TOKEN_ENV_NAME, None)
    auth = BearerToken(token=quay_token) if quay_token else None
    registry = Registry(auth=auth)
    repos = registry.list_repositories('weaveworks')
    pprint(repos)


if __name__ == '__main__':
    main()
