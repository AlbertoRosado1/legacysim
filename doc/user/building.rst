.. _user-building:

Building
========

The software stack is rather complicated. **legacysim** is a wrapper around **legacypipe**, which has many dependences.
So there are two methods for installing everything, Docker and from scratch.

legacysim with Docker
---------------------

Docker is the preferred method, as **legacysim** can be run from a laptop and NERSC using the same Docker image.
The Docker image is available on :dockerroot:`Docker Hub <>`.

On your laptop
^^^^^^^^^^^^^^

First pull::

  docker pull {dockerimage}

To run on-the-fly::

  docker run {dockerimage} ./yourscript.sh

Or in interactive mode, you can bind mount your working directory ``absolutepath``::

  docker run --volume absolutepath:/homedir/ -it {dockerimage} /bin/bash

which allows you to work as usual (type ``exit`` to exit).

On NERSC
^^^^^^^^

First pull::

  shifterimg -v pull {dockerimage}

To run on-the-fly::

  shifter --module=mpich-cle6 --image={dockerimage} ./yourscript.sh

In interactive mode::

  shifter --volume absolutepath:/homedir/ --image={dockerimage} /bin/bash

.. note::

  For further information on shifter, see `shifter docs`_.

legacysim from scratch
----------------------

To install **legacysim** from scratch, the simplest way is to follow instructions in the :root:`Travis file <.travis.yml>`:
first go through ``apt`` installs, then ``install``.

References
----------

.. target-notes::

.. _`shifter docs`: https://shifter.readthedocs.io/
