==========
quay-admin
==========

quay.io is pretty neat, but how do you know who has access to your repositories?

If you've got a small number of them, you can click through to each one and see who has what permissions.
But if you're an organization with a large number of repositories, it's very hard to see who can access your repositories.

In particular, when someone *leaves* your organization, how can you be sure that they can no longer upload images?

quay-admin is a simple command-line tool that shows which users who are *outside* your organization have access to which repositories.

For example:

.. code-block:: console

   $ QUAY_TOKEN=<YOUR_TOKEN_HERE> quay-admin woofshop
   woofshop/landscape
   - niceperson [admin]

   woofshop/spoonbridge
   - cooldude [admin]

   woofshop/thingdoer
   - dodgybloke [admin]

Installing
==========

.. code-block:: console

   $ pip install quayadmin

Running
=======

Everything is under the ``quay-admin`` command, which has its own help.

.. code-block:: console

   usage: quay-admin [-h] [--from-state FROM_STATE] [--api-root API_ROOT]
                     [--dump-state DUMP_STATE]
                     namespace

   Show information about quay.io permissions

   positional arguments:
     namespace             Namespace to look in

   optional arguments:
     -h, --help            show this help message and exit
     --from-state FROM_STATE
                           If provided, get quay.io state from a file, rather
                           than an API
     --api-root API_ROOT   Root of quay.io API. Ignored if --from-state provided.
     --dump-state DUMP_STATE
                           If provided, dump state to a file. Will overwrite file
                           if it exists.

To do anything useful, you will need an access token that has permission to "Administer Repositories".
See the `quay.io API documentation`_ for more information.

Running ``quay-admin`` will produce a text report of users who aren't in your organization
but who do have access to your repositories.
If such users exist, the script will exit with code 1.

The normal state is to gather data from quay.io.
However, you can save all that state with the ``--dump-state`` flag, and then load it later with ``--from--state``.
This can be useful for performing your own analysis, or developing new reporting functionality.


.. _`quay.io API documentation`: https://docs.quay.io/api/
