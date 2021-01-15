.. _user-example:

Example on NERSC
================

First, create your **legacysim** directory and copy/link the **legacy survey** data::

  mkdir -p ${CSCRATCH}/legacysim/dr9/data/
  cp {legacysurveyroot}ccds-annotated-* ${CSCRATCH}/legacysim/dr9/data/
  cp {legacysurveyroot}survey-* ${CSCRATCH}/legacysim/dr9/data/
  ln -s {legacysurveyroot}calib/ ${CSCRATCH}/legacysim/dr9/data/
  ln -s {legacysurveyroot}images/ ${CSCRATCH}/legacysim/dr9/data/

Next, clone the :root:`legacysim repo` and pull the docker image (see :ref:`user-building`)::

  cd
  git clone {gitrepo}
  shifterimg -v pull {dockerimage}

.. note::

  **legacysim** executable is in the Docker image. In the following we just use :root:`bin`.

Enter your shifter image, generate catalog of sources to be injected (see :ref:`user-pre-processing`)::

  shifter --volume ${HOME}:/homedir/ --image={dockerimage} /bin/bash
  cd legacysim/bin
  source legacypipe-env.sh
  python preprocess.py --do injected

Create run list, taking into account **legacypipe** versions used for bricks in ``$LEGACYPIPE_SURVEY_DIR/north/`` (see :ref:`user-running`)::

  python /src/legacysim/py/legacysim/scripts/runlist.py --outdir $LEGACYPIPE_SURVEY_DIR/north/ --brick bricklist.txt --write-list runlist.txt --modules docker

Exit the shifter image and run **legacysim** (see :ref:`user-running`)::

  exit
  srun -n 2 shifter --module=mpich-cle6 --volume ${HOME}:/homedir/ --image={dockerimage} ./mpi_runbricks.sh

Check everything ran, match and plot the comparison (see :ref:`user-post-processing`)::

  python /src/legacysim/py/legacysim/scripts/check.py --outdir $CSCRATCH/legacysim/dr9/test --brick bricklist_400N-EBV.txt
  python /src/legacysim/py/legacysim/scripts/match.py --cat-dir $CSCRATCH/legacysim/dr9/test/merged --outdir $CSCRATCH/legacysim/dr9/test --plot-hist plots/hist.png

You can also merge catalogs, plot cpu and memory usage, image cutouts::

  python /src/legacysim/py/legacysim/scripts/merge.py --filetype injected tractor --cat-dir $CSCRATCH/legacysim/dr9/test/merged --outdir $CSCRATCH/legacysim/dr9/test
  python /src/legacysim/py/legacysim/scripts/resources.py --outdir $CSCRATCH/legacysim/dr9/test --plot-fn plots/resources-summary.png
  python /src/legacysim/py/legacysim/scripts/cutout.py --outdir $CSCRATCH/legacysim/dr9/test --plot-fn "plots/cutout_%(brickname)s-%(icut)d.png" --ncuts 2
