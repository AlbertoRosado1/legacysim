.. _user-running:

Running
=======

Executable
----------

As in **legacypipe**, :mod:`~legacysim.runbrick` is the (main) executable.
Type ``python legacysim/runbrick.py --help`` to print the command line arguments.
**legacypipe** arguments are listed first, then in a separate group are **legacysim**-specific ones.

.. note::

  :mod:`~legacysim.runbrick` can be run from the command line or from a python script:

  .. code-block:: python

    from legacysim import runbrick
    runbrick.main(args)

  with arguments ``args``, as examplified in :root:`bin/mpi_main_runbricks.py`.

Environment manager
-------------------

An environment manager is provided in :mod:`~legacysim.batch.environment_manager`.
It sets up the environment variables as saved in the header of a **Tractor** (or **legacysim** injected sources) catalog.

.. code-block:: python

  from legacysim.batch import EnvironmentManager

  with EnvironmentManager(...):
      # do stuff

.. note::

  The environment variables can be set at run time by passing to :mod:`~legacysim.runbrick` ``--env-header`` with a catalog file name to get environment variables from.

To take into account the different package (e.g. **legacypipe**) versions used for each stage of **legacypipe** runs
(e.g. **tims**, **refs**, **srcs**, see `legacypipe runbrick <https://github.com/legacysurvey/legacypipe/blob/master/py/legacypipe/runbrick.py>`_), the ``PYTHONPATH`` must be set before running **legacysim**.
This ``PYTHONPATH`` as well as environment variables can be obtained (for a given brick name and stage) with :mod:`~legacysim.batch.environment_manager`.
This can be performed in Python as exemplified in :root:`bin/mpi_main_runbricks.py` or in bash as shown in :root:`bin/mpi_runbricks.sh`.


Run catalog
-----------

A class :class:`~legacysim.catalog.RunCatalog` is provided in **legacysim**.
It is a collection of brick names, simulation ids (fileid, rs, skipid; see :ref:`user-data-model`)
and stages (possibly with module versions) which uniquely identify **legacysim** runs.

.. code-block:: python

  from legacysim import RunCatalog

  runcat = RunCatalog.from_brick_sim_id(bricknames=['1588p560'],kwargs_simid=dict(fileid=0,rowstart=0,skipid=0))

  for run in runcat:
        print(run.brickname,run.fileid,run.rowstart,run.skipid,run.stages)

Brick may not be run with the same version of e.g. **legacypipe** for each stage,
which can be accounted for by splitting each **legacysim** run in stages using the same versions.
For this purpose :mod:`~legacysim.scripts.runlist` helps produce a run list (which can be read with :meth:`~legacysim.catalog.RunCatalog.from_list`) with runs split in stages.
Note that stage-splitting can be performed for a specific package (pass e.g. ``--modules legacypipe`` to :mod:`~legacysim.scripts.runlist`),
or for the full Docker image (pass ``--modules docker`` to :mod:`~legacysim.scripts.runlist`).

Task manager
------------

A task manager is provided in :mod:`~legacysim.batch.task_manager.py`.
It runs different tasks in series or in parallel within MPI. You can use it following:

.. code-block:: python

  from legacysim.batch import TaskManager

  with TaskManager(ntasks=...) as tm:

      for run in tm.iterate(runcat):
          # do stuff

Scripts
-------

Some scripts are available in the :root:`bin` directory:

* :root:`bin/runbrick.sh` to run a single brick, which can be easily modified to launch on a batch system.

* :root:`bin/mpi_runbricks.sh` to run bricks on several MPI ranks (can also be used without MPI).

.. note::

  The **legacypipe** environment variables are defined in :root:`bin/legacypipe-env.sh`.
  and **legacysim** settings (e.g. bricks to run) in :root:`bin/settings.py`.

.. note::

  The ``SURVEY_DIR`` directory should contain the directory ``images``, ``calib`` (if you not wish to rerun them),
  ``ccds-annotated-*`` and ``survey-*`` files.

On your laptop
^^^^^^^^^^^^^^

``runbrick.sh`` can be run within Docker through (``chmod u+x mpi_runbricks.sh`` if necessary)::

  docker run --volume $HOME:/homedir/ --image={dockerimage} ./mpi_runbricks.sh

``mpi_runbricks.sh`` can be run similarly; just add ``mpiexec`` or ``mpirun`` in front.

On NERSC
^^^^^^^^

:root:`bin/runbrick.sh`::

  shifter --volume $HOME:/homedir/ --image={dockerimage} ./mpi_runbricks.sh

:root:`bin/mpi_runbricks.sh`, without MPI::

  shifter --volume $HOME:/homedir/ --image={dockerimage} ./mpi_runbricks.sh

or with 2 MPI tasks::

  srun -n 2 shifter --module=mpich-cle6 --volume $HOME:/homedir/ --image={dockerimage} ./mpi_runbricks.sh

.. note::

  By default, :root:`bin/mpi_runbricks.sh` uses your current **legacysim** directory. To rather use the official release in the Docker image (``/src/legacysim``),
  uncomment ``export PYTHONPATH=...`` in :root:`bin/mpi_runbricks.sh`.

.. note::

  By default, :root:`bin/mpi_runbricks.sh` launches :root:`bin/mpi_main_runbricks.py` (which directly runs :mod:`~legacysim.runbrick`).
  To use :root:`bin/mpi_script_runbricks.sh` (which calls :root:`bin/runbrick.sh`) instead, pass the option ``-s``.

.. note::

  By default, :root:`bin/mpi_runbricks.sh` runs 8 OpenMP threads. You can change that using the ``OMP_NUM_THREADS`` environment variable.
