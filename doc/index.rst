.. title:: legacysim docs

*************************************
Welcome to legacysim's documentation!
*************************************

.. toctree::
  :maxdepth: 1
  :caption: User documentation

  user/building
  user/pre_processing
  user/running
  user/data_model
  user/post_processing
  user/example
  api/api

.. toctree::
  :maxdepth: 1
  :caption: Developer documentation

  developer/docker
  developer/documentation
  developer/tests
  developer/contributing
  developer/changes

.. toctree::
  :hidden:

************
Introduction
************

**legacysim** (previously `Obiwan`_) is a Monte Carlo method for adding fake galaxies to `Legacy Survey`_ images,
and re-processing the modified images with **legacypipe**.
The **legacypipe** documentation is available here: `legacypipe docs`_.


What for?
=========

Targets for spectroscopic follow-up are selected among the sources detected by **legacypipe**.
The target density includes cosmological clustering signal (to be measured) but is also impacted by so-called "imaging systematics",
due to the telescope, the opacity of the atmosphere, extinction and dust of the Milky Way, bias and variance of **legacypipe**.
These systematics can be (partly) removed by regressing the target density against photometric templates (linear model, or `neural nets`_),
but these methods can only remove dependence of the target density on *known* systematics.

**legacysim** rather forward models the source detection and target selection processes, by injecting fake galaxies into raw images,
running **legacypipe** and applying the target selection colour cuts.

**legacysim** was applied on `eBOSS ELGs`_.

Quick start-up
==============

For a quick start-up on NERSC, see :ref:`user-example`.

Acknowledgements
================

See the `offical acknowledgements <http://legacysurvey.org/#Acknowledgements>`_ for the Legacy Survey.

Changelog
=========

* :doc:`developer/changes`

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

References
==========

.. target-notes::

.. _`Obiwan`: https://obiwan.readthedocs.io/

.. _`Legacy Survey`: http://legacysurvey.org

.. _`legacypipe docs`: https://legacypipe.readthedocs.io/

.. _`neural nets`: https://arxiv.org/abs/1907.11355

.. _`eBOSS ELGs`: https://arxiv.org/abs/2007.08992
