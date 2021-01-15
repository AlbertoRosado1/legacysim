.. _developer-docker:

Building the Docker image
=========================

First create an account ``youraccount`` at `<https://hub.docker.com>`_.

To build, go into the root directory and run::

  docker-compose build

Or, alternatively::

   docker build -f docker/Dockerfile -t legacysim .

To tag and push::

  docker tag legacysim youraccount/legacysim:tag
  docker login
  docker push youraccount/legacysim:tag
