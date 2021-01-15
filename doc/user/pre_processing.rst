.. _user-pre-processing:

Pre-processing
==============

Random catalog
--------------

The catalog of sources to be injected (provided through ``--injected-fn``) should contain the following columns:

* ``ra``, ``dec`` (degree)

* ``flux_g``, ``flux_r``, ``flux_z``: including galactic extinction  (nanomaggies)

* ``sersic``: `Sersic index`_

* ``shape_r``, half light radius (arcsecond)

* ``shape_e1``, ``shape_e2``: `ellipticities`_

* ``seed``: random seed, to add noise

Examples of how to produce these catalogs are given in :root:`bin/preprocess.py`.

References
----------

.. target-notes::

.. _`Sersic index`: https://en.wikipedia.org/wiki/Sersic_profile

.. _`ellipticities`: https://www.legacysurvey.org/dr8/catalogs/
