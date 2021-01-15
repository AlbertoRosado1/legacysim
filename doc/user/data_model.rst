.. _user-data-model:

Data model
==========

In a nutshell, outputs are written in the following structure::

  test_brick
  |-- log
  |   `-- 135
  |       `-- 1351p192
  |           `-- file0_rs0_skip0
  |               `-- log.1351p192
  |-- injected
  |   `-- 135
  |       `-- 1351p192
  |           `-- file0_rs0_skip0
  |               |-- randoms-1351p192.fits
  |-- metrics
  |   `-- 135
  |       `-- 1351p192
  |           `-- file0_rs0_skip0
  |               |-- all-models-1351p192.fits
  |               `-- blobs-1351p192.fits.gz
  |-- tractor
  |   `-- 135
  |       `-- 1351p192
  |           `-- file0_rs0_skip0
  |               |-- brick-1351p192.sha256sum
  |               `-- tractor-1351p192.fits
  `-- tractor-i
  |    `-- 135
  |        `-- 1351p192
  |            `-- file0_rs0_skip0
  |                `-- tractor-1351p192.fits
  |-- coadd
  |   `-- 135
  |       `-- 1351p192
  |           `-- file0_rs0_skip0
  |               |-- legacysurvey-1351p192-ccds.fits
  |               |-- legacysurvey-1351p192-chi2-g.fits.fz
  |               |-- legacysurvey-1351p192-chi2-r.fits.fz
  |               |-- legacysurvey-1351p192-chi2-z.fits.fz
  |               |-- legacysurvey-1351p192-image-g.fits.fz
  |               |-- legacysurvey-1351p192-image-r.fits.fz
  |               |-- legacysurvey-1351p192-image-z.fits.fz
  |               |-- legacysurvey-1351p192-image.jpg
  |               |-- legacysurvey-1351p192-invvar-g.fits.fz
  |               |-- legacysurvey-1351p192-invvar-r.fits.fz
  |               |-- legacysurvey-1351p192-invvar-z.fits.fz
  |               |-- legacysurvey-1351p192-model-g.fits.fz
  |               |-- legacysurvey-1351p192-model-r.fits.fz
  |               |-- legacysurvey-1351p192-model-z.fits.fz
  |               |-- legacysurvey-1351p192-model.jpg
  |               |-- legacysurvey-1351p192-resid.jpg
  |               |-- legacysurvey-1351p192-sims-g.fits.fz
  |               |-- legacysurvey-1351p192-sims-r.fits.fz
  |               |-- legacysurvey-1351p192-sims-z.fits.fz
  |               `-- legacysurvey-1351p192-simscoadd.jpg

The top level output directory includes the following files:

* The usual six directories: **tractor**, **tractor-i**, **coadd**, **metrics**, **checkpoint**, **logs**

* Monte Carlo simulation metadata directory: **injected**

Subdirectories follow the usual Data Relase format of **.../bri/brick/**, where **bri** is the first three letters of each brick.
The multiple iterations per brick are identified by directories named **file[0-9]+_rs[0-9]+_skip[0-9]+**.

* **file[0-9]+** is the random file identifier.

* **rs** stands for the **row** of the unique id-sorted table of randoms in the brick to **start** from. **[0-9]+** is the index of that row, which would be 0, 500, 1000, etc. when 500 fake galaxies are added to the images in each iteration. For example, the tractor catalogues containing the first 1500 fake sources in brick **1757p240** are in:
  - .../tractor/135/1351p192/**file0_rs0_skip0**/
  - .../tractor/135/1351p192/**file0_rs500_skip0**/
  - .../tractor/135/1351p192/**file0_rs1000_skip0**/

* **skip$id** correspond to injected sources that were **skipped** in a previous $id-1 run (if $id>0), because in collision with another injected source.

* **skip$id** correspond to injected sources that were **skipped** in a previous $id-1 run (if $id>0), because in collision with another injected source.

The catalog of sources injected into images are stored in e.g. **../injected/135/1351p192/randoms-1351p192.fits**.
The column `collided` identifies collided sources, which were therefore not injected into images.
Command line arguments to :mod:`~legacysim.runbrick` are saved in the header.
