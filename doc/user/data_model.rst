.. _user-data-model:

Data model
==========

**legacysim** outputs are written in the following structure, similar to that of **legacypipe**::

  test
  `-- file0_rs0_skip0
      |-- logs
      |   `-- 135
      |       `-- log-1351p192.log
      |
      |-- sim
      |   `-- 135
      |       `-- injected-1351p192.fits
      |
      |-- metrics
      |   `-- 135
      |       |-- all-models-1351p192.fits
      |       `-- blobs-1351p192.fits.gz
      |
      |-- tractor
      |   `-- 135
      |       |-- brick-1351p192.sha256sum
      |       `-- tractor-1351p192.fits
      |
      |-- tractor-i
      |   `-- 135
      |       `-- tractor-1351p192.fits
      |
      `-- coadd
          `-- 135
              `-- 1351p192
                  |-- legacysurvey-1351p192-ccds.fits
                  |-- legacysurvey-1351p192-chi2-g.fits.fz
                  |-- legacysurvey-1351p192-chi2-r.fits.fz
                  |-- legacysurvey-1351p192-chi2-z.fits.fz
                  |-- legacysurvey-1351p192-image-g.fits.fz
                  |-- legacysurvey-1351p192-image-r.fits.fz
                  |-- legacysurvey-1351p192-image-z.fits.fz
                  |-- legacysurvey-1351p192-image.jpg
                  |-- legacysurvey-1351p192-invvar-g.fits.fz
                  |-- legacysurvey-1351p192-invvar-r.fits.fz
                  |-- legacysurvey-1351p192-invvar-z.fits.fz
                  |-- legacysurvey-1351p192-model-g.fits.fz
                  |-- legacysurvey-1351p192-model-r.fits.fz
                  |-- legacysurvey-1351p192-model-z.fits.fz
                  |-- legacysurvey-1351p192-model.jpg
                  |-- legacysurvey-1351p192-resid.jpg
                  |-- legacysurvey-1351p192-sims-g.fits.fz
                  |-- legacysurvey-1351p192-sims-r.fits.fz
                  |-- legacysurvey-1351p192-sims-z.fits.fz
                  `-- legacysurvey-1351p192-simscoadd.jpg

The top level output directory is split into subdirectories named **file%(fileid)d_rs%(rowstart)d_skip%(skipid)d**.

* **fileid** is the file identifier of injected sources.

* **rowstart** stands for the **row** of the catalog of sources to be injected in the brick to **start** from.
  For example, the **Tractor** catalogs containing the first 1500 sources (if 500 sources are added at each iteration,
  i.e. ``--nobj 500`` is passed to :mod:`legacysim.runbrick`) injected in brick **1757p240** are in:

  - .../**file0_rs0_skip0**/tractor/135/
  - .../**file0_rs500_skip0**/tractor/135/
  - .../**file0_rs1000_skip0**/tractor/135/

* **skipid** correspond to injected sources that were **skipped** in a previous skipid-1 run (if skipid>0), because in collision with another injected source.

The catalog of sources injected into images are stored in e.g. **.../file0_rs0_skip0/sim/135/injected-1351p192.fits**.
The column `collided` identifies collided sources, which were therefore **not** injected into images in this run.

Other subdirectories are the same as created by **legacypipe**.
