"""
**legacysim** is a Monte Carlo method for adding fake galaxies to Legacy Survey images and re-processing the modified images with the **legacypipe**.

Contains:
- runbrick.py : **legacysim** main executable, extend :mod:`legacypipe.runbrick`.
- survey.py : Classes to extend :mod:`legacypipe.survey`.
- image.py : Classes to extend :mod:`legacypipe.image`.
- catalog.py : Convenient classes to handle catalogs, bricks and runs.
- analysis.py : Convenient classes to perform **legacysim** analysis: image cutouts, catalog merging, catalog matching, computing time.
- utils.py : Convenient functions to handle **legacysim** inputs/outputs.
"""

from .version import __version__

__all__ = ['LegacySurveySim','get_randoms_id','find_file','find_legacypipe_file','find_legacysim_file']
__all__ += ['BaseCatalog','SimCatalog','BrickCatalog','RunCatalog','analysis','utils','setup_logging','batch']

from .survey import LegacySurveySim,get_randoms_id,find_file,find_legacypipe_file,find_legacysim_file
from .catalog import BaseCatalog,SimCatalog,BrickCatalog,RunCatalog
from .utils import setup_logging
