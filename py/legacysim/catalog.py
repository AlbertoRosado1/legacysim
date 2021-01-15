"""Convenient classes to handle catalogs, bricks and runs."""

import os
import re
import glob
import itertools
import logging
import argparse
import copy
from collections import UserDict,UserList

import numpy as np
import fitsio
from astrometry.util import fits
from legacypipe.survey import LegacySurveyData,wcs_for_brick

from .survey import find_file,get_randoms_id
from . import utils


logger = logging.getLogger('legacysim.catalog')


class BaseCatalog(fits.tabledata):
    """
    Extend :class:`~astrometry.util.fits.tabledata`, with convenient methods.

    Attributes
    ----------
    _length: int
        Catalog length, also given by :meth:`len` and :attr:`size`.

    _columns: list
        Catalog columns, including internals (starting with `_`). Without internals: :attr:`fields`.
    """

    def __init__(self, *args, **kwargs):
        """
        Call :func:`astrometry.util.fits.fits_table`.

        For an empty catalog, one can provide size or length, to define :meth:`len`,
        used in methods to build ``numpy`` arrays (e.g. :meth:`zeros`).
        Otherwise, :meth:`len` is set when the first column is added.
        """
        length = kwargs.pop('length',kwargs.pop('size',None))
        table = fits.fits_table(*args,**kwargs)
        self.__dict__.update(table.__dict__)
        if length is not None: self._length = length

    def __getitem__(self, item):
        """Redefine :meth:`astrometry.util.fits.tabledata.__getitem__` to avoid calling :meth:`__init__`."""
        toret = self.copy(fields=[])
        for name,val in self.__dict__.items():
            if name.startswith('_'):
                continue
            if name in self and len(self) < 2:
                val = np.atleast_1d(val)
            col = fits.cut_array(val, item, name)
            toret.set(name, col)
            if np.isscalar(item):
                toret._length = 1
            else:
                toret._length = len(getattr(toret, name))
        return toret

    @classmethod
    def from_dict(cls, d):
        """Construct catalog from dictionary of (field, column)."""
        self = cls()
        for key,val in d.items():
            self.set(key,val)
        return self

    @property
    def size(self):
        """Return :meth:`len`."""
        return len(self)

    @property
    def fields(self):
        """Return ``fields = self.get_columns(internal=False)``."""
        return self.get_columns(internal=False)

    def __contains__(self, name):
        """Is there a column ``name``?"""
        return (name in self.fields)

    def zeros(self, dtype=np.float64):
        """Return array of size :attr:`size` filled with zero."""
        return np.zeros(len(self),dtype=dtype)

    def ones(self, dtype=np.float64):
        """Return array of size :attr:`size` filled with one."""
        return np.ones(len(self),dtype=dtype)

    def falses(self):
        """Return array of size :attr:`size` filled with ``False``."""
        return self.zeros(dtype=np.bool_)

    def trues(self):
        """Return array of size :attr:`size` filled with ``True``."""
        return self.ones(dtype=np.bool_)

    def nans(self):
        """Return array of size :attr:`size` filled with :attr:`numpy.nan`."""
        return self.ones()*np.nan

    def full(self,*args,**kwargs):
        """Call :func:`numpy.full` with shape :attr:`size`."""
        return np.full(self.size,*args,**kwargs)

    def index(self):
        """Return zero-starting index."""
        return np.arange(self.size)

    def delete_columns(self, *fields):
        """Delete columns ``fields``."""
        for field in fields:
            self.delete_column(field)

    def keep_columns(self, *fields):
        """Keep only columns ``fields``."""
        for field in self.fields:
            if field not in fields:
                self.delete_column(field)

    def fill(self, other, index_self=None, index_other=None, fields_other=None, fill_nan=True):
        """
        Fill (or create) columns with those of ``other`` catalog.

        If a column of name ``field`` already exists in ``self`` (with a shape compatible with that of ``other``),
        the values with indices ``index_self`` are replaced by those of ``other`` with indices ``index_other``.
        Else, a new column is added to ``self``, with default value given by :func:`numpy.zeros` (or :attr:`numpy.nan` if ``fill_nan == True``).
        Again, the values with indices ``index_self`` are replaced by those of ``other`` with indices ``index_other``.

        Parameters
        ----------
        other : BaseCatalog
            Catalog to be merged to ``self``.

        index_self : slice, ndarray, string, default=None
            Indices (or bool mask) of ``self`` to fill with ``other``.
            If ``None``, all indices of ``self`` are considered.
            If `before`, ``other[index_other]`` rows are added at the beginning of ``self``.
            If `after`, ``other[index_other]`` rows are added at the end of ``self``.

        index_other : slice, ndarray, default=None
            Indices (or bool mask) of ``other`` to fill ``self``.
            If ``None``, all indices of ``other`` are considered.

        fields_other : list, default=None
            Fields of ``other`` to be added to ``self``.
            If ``None``, all fields of other are considered.

        fill_nan : bool, default=True
            If ``True``, default value for added column is :attr:`numpy.nan` instead of :func:`numpy.zeros`.
        """
        if index_self is None:
            index_self = self.trues()
        if index_other is None:
            index_other = other.trues()
        if fields_other is None:
            fields_other = other.fields

        other_size = other.get(fields_other[0])[index_other].size

        def isfloating(dtype):
            return isinstance(np.zeros(1,dtype=dtype)[0],np.floating)

        if isinstance(index_self,str):
            index_self_ = index_self
            totalsize = self.size + other_size
            if index_self_ == 'before':
                index_self = slice(0,other_size)
            elif index_self_ == 'after':
                index_self = slice(self.size,totalsize)
            else:
                raise ValueError('If string, index_self should be either "before" or "after"')
            for field in self.fields:
                col_self = self.get(field)
                col_new = np.zeros(shape=(other_size,)+col_self.shape[1:],dtype=col_self.dtype)
                if fill_nan and isfloating(col_self.dtype):
                    col_new[...] = np.nan
                if index_self_  == 'before':
                    col_new = np.concatenate([col_new,col_self])
                elif index_self_  == 'after':
                    col_new = np.concatenate([col_self,col_new])
                self.set(field,col_new)
            self._length = totalsize

        for field in fields_other:
            col_other = other.get(field)
            if field in self.fields:
                col_self = self.get(field)
                if col_self.shape[1:] != col_other.shape[1:]: # other column overrides
                    self.delete_column(field)
            if field not in self.fields:
                col_self = np.zeros(shape=(self.size,)+col_other.shape[1:],dtype=col_other.dtype)
                if fill_nan and isfloating(col_self.dtype):
                    col_self[...] = np.nan
            col_self[index_self] = col_other[index_other]

            self.set(field,col_self)

    def copy(self, fields=None):
        """
        Return a (deep) copy, keeping columns ``fields``.

        Parameters
        ----------
        fields : string, list, default=None
            Single field or list of fields. If ``None``, use all fields.

        Returns
        -------
        new : BaseCatalog
            Copy.

        Note
        ----
        Contrary to :class:`astrometry.util.fits.tabledata`, all internal (starting with '_') values are (deep) copied.
        """
        if fields is None:
            fields = self.fields
        if isinstance(fields,str):
            fields = [fields]
        new = object.__new__(self.__class__)
        for name,val in self.__dict__.items():
            if name.startswith('_') or name in fields:
                new.set(name,copy.deepcopy(val))
            new._columns = fields
        return new

    def __eq__(self, other):
        """Is ``self == other`` (same type, :attr:`size` and colums)?"""
        if not type(other) is self.__class__:
            return False
        if not set(self.fields) == set(other.fields):
            return False
        if not self.size == other.size:
            return False
        if self.size == 0:
            return True
        for field in self.fields:
            if isinstance(self.get(field).flat[0],np.floating):
                mask = ~np.isnan(self.get(field))
                if not np.all(self.get(field)[mask] == other.get(field)[mask]):
                    return False
            else:
                if not np.all(self.get(field) == other.get(field)):
                    return False
        return True

    def __radd__(self, other):
        """Right add: ``self + other``."""
        if other == 0:
            return self.copy()
        return self.__add__(other)

    def __ladd__(self, other):
        """Left add: ``other + self``."""
        if other == 0:
            return self.copy()
        return self.__add__(other)

    def __add__(self, other):
        """
        Append ``self`` and ``other`` catalogs and return a new instance ``new``.

        ``len(new) == len(self) + len(other)``
        """
        new = self.copy()
        if other == 0:
            return new
        if not other.fields: #empty catalog
            return new
        new.append(other)
        return new

    def to_recarray(self, fields=None):
        """
        Return :class:`numpy.recarray` representation for columns ``fields``.

        Parameters
        ----------
        fields : string, list, default=None
            Single field or list of fields. If ``None``, use all fields.

        Returns
        -------
        array : recarray
            :class:`numpy.recarray` instance.
        """
        if fields is None:
            fields = self.fields
        if isinstance(fields,str):
            fields = [fields]
        return np.rec.fromarrays([self.get(field) for field in fields],names=fields)

    def to_ndarray(self, fields=None):
        """
        Return :class:`numpy.ndarray` representation for columns ``fields``.

        Parameters
        ----------
        fields : string, list, default=None
            Single field or list of fields. If ``None``, use all fields.

        Returns
        -------
        array : ndarray
            :class:`numpy.ndarray` instance.
        """
        return np.array(self.to_recarray(fields=fields))

    def unique(self, fields=None, sort_index=False, return_unique=True, **kwargs):
        """
        Return catalog with unique rows for columns ``fields``.

        Parameters
        ----------
        fields : string, list, default=None
            Single field or list of fields. If ``None``, use all fields.

        sort_index : bool, default=False
            Sort by increasing index.

        return_unique : bool, default=True
            Return catalog with unique rows for columns ``fields``.

        kwargs : dict
            Other arguments for :func:`numpy.unique`.

        Returns
        -------
        unique : BaseCatalog
            If ``return_unique == True``, return catalog with unique rows.
            For other values see :func:`numpy.unique`.
        """
        return_index = kwargs.get('return_index',False)
        if sort_index:
            kwargs = {**kwargs,**{'return_index':True}}
        toret = np.unique(self.to_ndarray(fields), axis=0, **kwargs)
        if not isinstance(toret,tuple):
            toret = (toret,)
        if sort_index:
            argsort = np.argsort(toret[1])
            if not return_index:
                toret = (toret[0],) + toret[2:]
            tmp = toret
            toret = (tmp[0][argsort],)
            i = 0
            if return_index:
                i += 1
                toret = toret + (tmp[i][argsort],)
            if kwargs.get('return_inverse',False):
                i += 1
                toret = toret + (argsort[tmp[i]],)
            for j in range(i+1,len(tmp)):
                toret = toret + (tmp[j][argsort],)
        if return_unique:
            cat = self.copy(fields=[])
            for name in toret[0].dtype.names:
                cat.set(name,toret[0][name])
            cat._length = toret[0].size
            if len(toret) == 1:
                return cat
            return (cat,) + toret[1:]
        toret = toret[1:]
        if len(toret) == 1:
            return toret[0]
        return toret

    def remove_duplicates(self, fields=None, copy=False):
        """
        Remove duplicate rows for ``fields``.

        Returned catalog has the same fields as ``self``.

        Parameters
        ----------
        fields : string, list, default=None
            Single field or list of fields. If ``None``, use all fields.

        copy : bool, default=False
            Return copy?

        Returns
        -------
        se;f : BaseCatalog
            Catalog without duplicate rows.
        """
        indices = self.unique(fields=fields,return_unique=False,return_index=True,sort_index=True)
        if copy:
            return self[indices]
        for field in self.fields:
            self.set(field,self.get(field)[indices])
            self._length = indices.size
        return self

    def uniqid(self, fields=None):
        """
        Return unique id for ``fields``.

        Parameters
        ----------
        fields : string, list, default=None
            Single field or list of fields. If ``None``, use all fields.

        Returns
        -------
        array : ndarray
            :class:`numpy.ndarray` strings with shape :attr:`size`.
        """
        if fields is None:
            fields = self.fields
        if isinstance(fields,str):
            fields = [fields]
        rows = np.array([self.get(field) for field in fields]).T
        return np.array(['-'.join(row) for row in rows])

    def isin(self, other, fields=None):
        """
        Return mask selecting rows that are in ``other`` for ``fields``.

        Parameters
        ----------
        other : BaseCatalog
            Other catalog.

        fields : string, list, default=None
            Single field or list of fields. If ``None``, use all fields.

        Returns
        -------
        mask : bool ndarray
            Mask.
        """
        if fields is None:
            fields = self.fields
        if isinstance(fields,str):
            fields = [fields]
        selfid,otherid = self.uniqid(fields=fields),other.uniqid(fields=fields)
        return np.isin(selfid,otherid)

    def tile(self, repeats, copy=True):
        """
        Apply :func:`numpy.tile` to every column.

        Parameters
        ----------
        repeats : int
            Number of repeats.

        copy : bool, default=False
            Return copy?

        Returns
        -------
        new : BaseCatalog
            Tiled catalog.
        """
        new = self
        if copy:
            new = self.copy(fields=[])
        new._length = repeats * self._length
        for field in self.fields:
            new.set(field,np.tile(self.get(field),repeats))
        return new

    def repeat(self, repeats, copy=True):
        """
        Apply :func:`numpy.repeat` to every column.

        Parameters
        ----------
        repeats : int
            Number of repeats.

        copy : bool, default=False
            Return copy?

        Returns
        -------
        new : BaseCatalog
            Repeated catalog.
        """
        new = self
        if copy:
            new = self.copy(fields=[])
        new._length = repeats * self._length
        for field in self.fields:
            new.set(field,np.repeat(self.get(field),repeats,axis=0))
        return new

    def writeto(self, fn, *args, **kwargs):
        """Write to ``fn``."""
        logger.info('Writing %s to %s.',self.__class__.__name__,fn)
        utils.mkdir(os.path.dirname(fn))
        super(BaseCatalog,self).writeto(fn,*args,**kwargs)


class SimCatalog(BaseCatalog):
    """Extend :class:`BaseCatalog` with convenient methods for **legacysim** randoms."""

    def fill_legacysim(self, survey=None):
        """
        Fill ``self`` with columns required for **legacysim** (if not already in ``self``):

            - ``id`` : defaults to :meth:`index`
            - ``brickname``, (brick) ``bx``, ``by`` coordinates: based on ``survey`` and ``ra``, ``dec``.

        Columns mandatory for **legacysim** are:

            - ``ra``, ``dec`` : coordinates (degree)
            - ``flux_g``, ``flux_r``, ``flux_z`` : including galactic extinction (nanomaggies)
            - ``sersic`` : Sersic index
            - ``shape_r`` : half light radius (arcsecond)
            - ``shape_e1``, ``shape_e2`` : ellipticities.

        Parameters
        ----------
        survey : LegacySurveyData, string, default=None
            ``survey_dir`` or survey. Used to determine brick-related quantities (``brickname``, ``bx``, ``by``).
            If ``None``, brick-related quantities are inferred from :class:`desiutil.brick.Bricks` (see :class:`BrickCatalog`).

        References
        ----------
        https://en.wikipedia.org/wiki/Sersic_profile
        https://www.legacysurvey.org/dr8/catalogs
        """
        bricks = None
        if 'brickname' not in self:
            bricks = BrickCatalog(survey=survey)
            self.brickname = bricks.get_by_radec(self.ra,self.dec).brickname

        if 'id' not in self:
            self.id = self.index()

        if 'bx' not in self:
            if bricks is None: bricks = BrickCatalog(survey=survey)
            self.bx,self.by = bricks.get_xy_from_radec(self.ra,self.dec,brickname=self.brickname)

    def mask_collisions(self, radius_in_degree=5./3600.):
        """
        Return mask of collided objects.

        Calls :func:`utils.mask_collisions`.

        Parameters
        ----------
        radius_in_degree : float, default=5./3600.
            Collision radius (degree).

        Returns
        -------
        mask : bool ndarray
            Mask of collided objects.
        """
        return utils.mask_collisions(self.ra,self.dec,radius_in_degree=radius_in_degree)

    def match_radec(self, other, radius_in_degree=5./3600., **kwargs):
        """
        Match ``self`` and ``other`` ``ra``, ``dec``.

        Calls :func:`utils.match_radec`.

        Parameters
        ----------
        other : SimCatalog
            Catalog to be matched against ``self``.

        radius_in_degree : float, default=5./3600.
            Collision radius (degree).

        kwargs : dict
            Arguments for :func:`utils.match_radec`.

        Returns
        -------
        index_self : ndarray
            Indices of matching points in ``self``.

        index_other : ndarray
            Indices of matching points in ``other``.
        """
        return utils.match_radec(self.ra,self.dec,other.ra,other.dec,radius_in_degree,**kwargs)

    def get_extinction(self, band, camera='DES'):
        """
        Return SFD extinction given ``band`` and ``camera``.

        Calls :func:`utils.get_extinction`.

        Parameters
        ----------
        band : string
            Photometric band.

        camera : string, default=`DES`
            camera.

        Returns
        -------
        extinction : ndarray
            Extinction (mag).
        """
        return utils.get_extinction(self.ra,self.dec,band=band,camera=camera)


class BrickCatalog(BaseCatalog):
    """
    Extend :class:`BaseCatalog` with convenient methods for bricks.

    Attributes
    ----------
    _rowmax, _colmax, _ncols : int, int, ndarray
        internals to grep brick from ra, dec (see :meth:`get_by_radec`).

    hash : ndarray
        Hash table to grep brick from ra, dec.

    columns : ndarray
        ``brickname``, ``brickid``, etc.
    """

    def __init__(self, survey=None):
        """
        Load bricks.

        Parameters
        ----------
        survey : LegacySurveyData, string, default=None
            ``survey_dir`` or ``survey``.
            If ``None``, construct :class:`BrickCatalog` from :class:`desiutil.brick.Bricks`.
        """
        if survey is not None:
            if not isinstance(survey,LegacySurveyData):
                survey = LegacySurveyData(survey_dir=survey)
            bricks_fn = survey.find_file('bricks')
            logger.info('Reading bricks from %s',bricks_fn)
            super(BrickCatalog,self).__init__(bricks_fn)
        else:
            logger.info('Building bricks from desiutil.brick')
            from desiutil.brick import Bricks
            table = Bricks().to_table()
            super(BrickCatalog,self).__init__(table,use_fitsio=False)
            self.to_np_arrays()
        assert np.all(self.brickid == 1+self.index())
        self._rowmax = self.brickrow.max()
        self._colmax = self.brickcol.max()
        self._ncols = np.bincount(self.brickrow)
        # should be applied mask as other columns, so no _
        self.hash = self.brickrow * (self._colmax + 1) + self.brickcol

    def get_hash(self):
        """Return :attr:`hash` enforcing at least 1d (contrary to e.g. ``self[0].hash``)."""
        return np.atleast_1d(self.hash)

    def get_by_name(self, brickname):
        """
        Return bricks with name ``brickname``.

        Parameters
        ----------
        brickname : string, array-like
            If string, return a single-element :class:`BrickCatalog`, else a :class:`BrickCatalog` with defined :attr:`size`.

        Returns
        -------
        bricks : BrickCatalog
            ``self`` cut to ``brickname``.
        """
        if np.isscalar(brickname):
            index = np.flatnonzero(self.brickname == brickname)[0]
        else:
            uniques,inverse = np.unique(brickname,return_inverse=True)
            index = np.array([np.flatnonzero(self.brickname == brickname_)[0] for brickname_ in uniques])[inverse]
        return self[index]

    def get_by_radec(self, ra, dec):
        """
        Return bricks containing ``ra``, ``dec``.

        Parameters
        ----------
        ra : float, array-like
            Right ascension (degree).

        dec : float, array-like
            Declination (degree).

        Returns
        -------
        bricks : BrickCatalog
            ``self`` cut to bricks containing ``ra``, ``dec``.
        """
        if not np.isscalar(ra):
            ra, dec = np.array(ra), np.array(dec)
        row = np.int32(np.floor(dec * self._rowmax / 180. + 360. + 0.5))
        row = np.clip(row, 0, self._rowmax)
        ncols = self._ncols[row]
        col = np.int32(np.floor(ra * ncols / 360. ))
        ind = self.get_hash().searchsorted(row * (self._colmax + 1) + col)
        return self[ind]

    def get_radecbox(self, total=False):
        """
        Return ra, dec box (ramin, ramax, decmin, decmax) of individual bricks.

        Parameters
        ----------
        total : bool, default=False
            If ``True``, returns the ra, dec box enclosing all bricks.

        Returns
        -------
        (ramin, ramax, decmin, decmax) : tuple of float, ndarray
            ra, dec box.
        """
        toret = [self.get(key) for key in ['ra1','ra2','dec1','dec2']]
        if total:
            toret = [np.min(toret[0]),np.max(toret[1]),np.min(toret[2]),np.max(toret[3])]
        return toret

    def get_area(self, total=False):
        """
        Return area of individual bricks.

        Calls :func:`utils.get_radecbox_area`.

        Parameters
        ----------
        total : bool, default=False
            If ``True``, returns total area.

        Returns
        -------
        area : float, ndarray
            Area (degree^2).
        """
        area = utils.get_radecbox_area(self.ra1,self.ra2,self.dec1,self.dec2)
        if total:
            area = np.sum(area)
        return area

    def get_xy_from_radec(self, ra, dec, brickname=None):
        """
        Returns brick ``bx``, ``by`` given ``ra``, ``dec``.

        Parameters
        ----------
        ra : float, array-like
            Right ascension (degree).

        dec : float, array-like
            Declination (degree).

        brickname : string, array-like, default=None
            Brick name. If array-like, should be of the same length as ``ra``, ``dec``.
            If ``None``, will query the correct ``brickname`` given ``ra``, ``dec``.

        Returns
        -------
        bx : float, ndarray
            Brick x coordinate.

        by : float, ndarray
            Brick y coordinate.
        """
        if np.isscalar(brickname):
            bx, by = wcs_for_brick(self.get_by_name(brickname)).radec2pixelxy(ra,dec)[1:]
            return bx-1, by-1 # legacyipe convention: zero-indexed
        if brickname is None:
            brickname = np.atleast_1d(self.get_by_radec(ra,dec).brickname)
        isscalar = np.isscalar(ra)
        ra,dec = np.atleast_1d(ra),np.atleast_1d(dec)
        brickname = np.asarray(brickname)
        bx,by = np.zeros_like(ra),np.zeros_like(dec)
        for brickname_ in np.unique(brickname):
            mask = brickname == brickname_
            bx[mask],by[mask] = self.get_xy_from_radec(ra[mask],dec[mask],brickname_)
        if isscalar:
            return bx[0],by[0]
        return bx,by

    def write_list(self, fn):
        """
        Write brick names to ``fn``.

        Parameters
        ----------
        fn : string
            Path to brick list.
        """
        utils.mkdir(os.path.dirname(fn))
        with open(fn,'w') as file:
            for brickname in self.brickname:
                file.write('%s\n' % brickname)

    @staticmethod
    def read_list(bricklist, unique=True):
        """
        Read brick list and return list of (unique) brick names.

        Parameters
        ----------
        bricklist : list, string
            List of strings (or one string) corresponding either brick names or ASCII files containing a column of brick names.

        unique : bool, default=True
            Return unique brick names?

        Returns
        -------
        bricknames : list
            List of (unique) brick names.
        """
        bricknames = []
        if np.isscalar(bricklist): bricklist = [bricklist]
        for brickname in bricklist:
            if os.path.isfile(brickname):
                logger.info('Reading brick list %s',brickname)
                with open(brickname,'r') as file:
                    for line in file:
                        brickname = line.replace('\n','')
                        if (not unique) or (brickname not in bricknames):
                            bricknames.append(brickname)
            else:
                if (not unique) or (brickname not in bricknames):
                    bricknames.append(brickname)
        return bricknames


class Versions(UserDict):
    """Handle (module,version) mapping. No order relation."""

    def __init__(self, *args, **kwargs):
        """
        If no ``args`` provided, ``kwargs`` should contain (module,version) mapping.
        If one ``args`` provided, can be:

            - a dictionary of (key,value) = (module,version)
            - a list of tuples: '[(module1,version1), (module2,version2)]'
            - a list of strings: '['module1:version1', 'module2:version2']'
            - a string: 'module1:version1,module2:version2'
        """
        if len(args) == 0:
            self.data = kwargs
        elif len(args) == 1:
            args = args[0]
            self.data = {}
            if isinstance(args,(UserDict,dict)):
                self.data = args
                return
            if isinstance(args,str):
                args = args.split(',')
            for mv in args:
                if isinstance(mv,str):
                    m,v = mv.split(':',maxsplit=1)
                else:
                    m,v = mv
                self.data[m] = v
        else:
            raise ValueError('Incorrect number of args %d, expected <= 1' % len(args))

    def keys(self):
        """Return keys sorted by alphanumeric order."""
        return sorted(self.data.keys())

    def __iter__(self):
        """Iterate."""
        return iter(self.keys())

    def __repr__(self):
        """String representation."""
        return ','.join(['%s:%s' % (key,self[key]) for key in self])

    def __bool__(self):
        """Is ``True``?"""
        return bool(self.data)


class Stages(UserDict):
    """
    Handle (stage,versions) mapping. Keys sorted in :mod:`legacypipe.runbrick` chronological order.

    Attributes
    ----------
    _all : list
        All stages of :mod:`legacypipe.runbrick`.

    _default : string
        Default stage name.
    """
    _all = ['tims','refs','outliers','halos','srcs','fitblobs','coadds','wise_forced','writecat']
    _default = 'writecat'

    def __init__(self, stages=None):
        """
        If ``stages`` is ``None``, include only stage 'writecat'.
        Else, ``stages`` can be:

            - a dictionary of (key,value) = (stage,versions)
            - a list of tuples: '[(stage1,versions1), (stage2,versions2)]'
            - a list of strings: '['stage1:versions1', 'stage2:versions2']'
            - a string: 'stages1:versions1 stages2:versions2'
        """
        if stages is None:
            self.data = {self._default:Versions()}
        else:
            if isinstance(stages,(UserDict,dict)):
                self.data = {key:Versions(val) for key,val in stages.items()}
                return
            self.data = {}
            if isinstance(stages,str):
                stages = stages.split()
            for stage in stages:
                if isinstance(stage,str):
                    nv = stage.split(':',maxsplit=1)
                    if len(nv) == 2:
                        self.data[nv[0]] = Versions(nv[1])
                    else:
                        self.data[nv[0]] = Versions()
                else:
                    n,v = stage
                    self.data[n] = Versions(v)

    def keys(self):
        """Return keys sorted by chronological order in :mod:`legacypipe.runbrick`."""
        return sorted(self.data.keys(),key=lambda v: self._all.index(v) if v in self._all else -1)

    @classmethod
    def all(cls):
        """Return :attr:`_all`."""
        return cls._all

    @classmethod
    def default(cls):
        """Return :attr:`_default`."""
        return cls._default

    def __iter__(self):
        """Iterate."""
        return iter(self.keys())

    def without_versions(self):
        """Return copy with empty versions."""
        key = self.keys()[-1]
        toret = self.__class__({key:self.data[key]})
        toret[key] = Versions()
        return toret

    def __repr__(self):
        """String representation."""
        return ' '.join(['%s:%s' % (key,val) if val else key for key,val in self.items()])

    def isin(self, other):
        """
        Return mask selecting stages of ``self`` that are in ``other``.

        Parameters
        ----------
        other : Stages
            Other stages.

        Returns
        -------
        mask : list
            Mask.
        """
        mask = []
        for name in self:
            if name in other and self[name] == other[name]:
                mask.append(True)
            else:
                mask.append(False)
        return mask


class ListStages(UserList):
    """Handle list of unique stages."""

    def __init__(self, args=None):
        """``args`` must be a list of stages."""
        self.data = []
        if args is not None:
            for arg in args:
                self.append(arg)

    def append(self, *args, **kwargs):
        """Append stages, return current index."""
        new = Stages(*args, **kwargs)
        if new not in self:
            self.data.append(new)
            return len(self) - 1
        return self.index(new)

    def without_versions(self):
        """
        Return copy with empty versions and its list of indices matching ``self``,

        Returns
        -------
        new : ListStages
            Versions are all empty.

        istages : list
            List of indices, such that::

                for iself,inew in enumerate(istages):
                    # iself is the index in self
                    # inew is the corresponding index in new

        """
        new = self.__class__()
        istages = []
        for stages in self:
            istages.append(new.append(stages.without_versions()))
        return new,istages

    def index(self, stages):
        """Return index of stages if in ``self``, else -1."""
        if stages in self:
            return self.data.index(stages)
        return -1

    def match(self, other):
        """
        Match list stages.

        Parameters
        ----------
        other : Stages
            Other stages.

        Returns
        -------
        istages1 : list
            The list of indices in ``self`` matching ``other``, such that::
                for iother,iself in enumerate(istages1):
                    # iself is the index in self
                    # iother is the corresponding index in other

        istages2 : list
            The list of indices in ``other`` matching ``self``.
        """
        return [self.index(stages) for stages in other],[other.index(stages) for stages in self]


class RunCatalog(BaseCatalog):
    """
    Extend ``BaseCatalog`` with convenient methods for run (defined by brick x randoms id x stages id) lists.

    Useful to schedule jobs and navigate through the **legacysim** or **legacypipe** file structure.

    Attributes
    ----------
    _list_stages : ListStages
        List of stages corresponding to indices in column ``stagesid``.
    """

    def __init__(self, dataorfn=None, header=None, **kwargs):
        """Initialize ``RunCatalog`` from array or file name."""
        super(RunCatalog,self).__init__(dataorfn=dataorfn,header=header,**kwargs)
        self._list_stages = ListStages()
        if header is None and isinstance(dataorfn,str):
            header = fitsio.read_header(dataorfn)
        if header is not None:
            for key in header:
                match = re.match('STAGES(?P<i>.*?)$',key)
                if match is not None:
                    istages = self.append_stages(header[key])
                    i = int(match.group('i'))
                    if istages != i:
                        raise ValueError('Stage header is incorrect: stage ID (%d) does not match stage order (%d).' % (i,istages))

    def writeto(self, *args, primheader=None, **kwargs):
        """Write catalog, saving stages in header."""
        runcat = self.remove_duplicates(copy=True).update_stages()
        runcat.check()
        if primheader is None:
            primheader = fitsio.FITSHDR()
        for istages,stages in enumerate(runcat.get_list_stages()):
            primheader.add_record(dict(name='STAGES%d' % istages,value=str(stages),comment='Stages corresponding to ID %d' % istages))
        super(RunCatalog,runcat).writeto(*args,primheader=primheader,**kwargs)

    @staticmethod
    def get_input_parser(parser=None, add_stages=False):
        """
        Add parser arguments to define runs.

        Parameters
        ----------
        parser : argparse.ArgumentParser, default=None
            Parser to add (in place) arguments to. If ``None``, a new one is created.

        add_stages : bool, default=False
            Add argument '--stages'?

        Returns
        -------
        parser : argparse.ArgumentParser
            Parser with arguments.
        """
        if parser is None:
            parser = argparse.ArgumentParser()
        for key in get_randoms_id.keys():
            parser.add_argument('--%s' % key, nargs='*', type=int, default=None, help='Use these %ss.' % key)
        parser.add_argument('--brick', nargs='*', type=str, default=None, help='Use these brick names. Can be a brick list file.')
        parser.add_argument('--list', nargs='*', type=str, default=None, help='Use these run lists.')
        if add_stages:
            parser.add_argument('--stages', nargs='*', type=str, default=None, help='Use these stages.')
        return parser

    @staticmethod
    def get_output_parser(parser=None, add_stages=False, add_filetype=False, add_source=False):
        """
        Add parser arguments to reconstruct runs from **legacypipe** or **legacysim** file structure.

        Parameters
        ----------
        parser : argparse.ArgumentParser, default=None
            Parser to add (in place) arguments to. If ``None``, a new one is created.

        add_stages : bool, default=False
            Add argument '--stages' and '--pickle'?

        add_filetype : bool, default=False
            Add argument '--filetype'?

        add_source : bool, default=False
            Add argument '--source'?

        Returns
        -------
        parser : argparse.ArgumentParser
            Parser with arguments.
        """
        if parser is None:
            parser = argparse.ArgumentParser()
        parser.add_argument('-d', '--outdir', dest='output_dir', type=str, default='.', help='Output base directory, default "."')
        RunCatalog.get_input_parser(parser,add_stages=add_stages)
        if add_stages:
            parser.add_argument('-P', '--pickle', dest='pickle_pat', type=str, default=None, help= 'Pickle file name pattern; \
                                                                                            if not provided, used the default file name (in "outdir/pickle")')
        if add_filetype:
            parser.add_argument('--filetype', type=str, default=None, help='File type to search for.')
        if add_source:
            parser.add_argument('--source', type=str, choices=['legacysim','legacypipe'], default='legacysim', help='legacypipe or legacysim file structure?')
        return parser

    @staticmethod
    def kwargs_files_from_cmdline(opt):
        """
        Return list of :class:`legacysim.survey.get_randoms_id` dictionaries from command-line arguments.

        Parameters
        ----------
        opt : argparse.Namespace, dict
            Holds options of :meth:`get_input_parser`.

        Returns
        -------
        kwargs_files : dict list
            List of :class:`~legacysim.survey.get_randoms_id` dictionaries.
        """
        if isinstance(opt,dict):
            opt = dict(opt)
        else:
            opt = vars(opt)
        for key,default in zip(get_randoms_id.keys(),get_randoms_id.default()):
            if opt[key] is None:
                opt[key] = [default]

        args = np.atleast_2d(np.array([opt[key] for key in get_randoms_id.keys()]).T)
        kwargs_files = []
        for arg in args:
            kwargs_files.append(dict(zip(get_randoms_id.keys(),arg)))
        return kwargs_files

    @classmethod
    def from_input_cmdline(cls, opt):
        """
        Initialize :class:`RunCatalog` from command-line arguments of :meth:`get_input_parser`.

        If 'list' is not ``None``, create new instance with :meth:`from_list`.
        and apply :meth:`mask_cmdline` i.e. restrict to those runs corresponding to other arguments in ``opt`` (ignore if ``None``).
        Else ('list' is ``None``), create new instance with :meth:`from_brick_randoms_id` based on other command-line arguments.

        Parameters
        ----------
        opt : argparse.Namespace, dict
            Holds options of :meth:`get_input_parser`.

        Returns
        -------
        self : RunCatalog
            New instance.
        """
        if isinstance(opt,dict):
            opt = dict(opt)
        else:
            opt = vars(opt)
        for key in ['list','brick'] + get_randoms_id.keys() + ['stages']:
            opt.setdefault(key,None)

        if opt['brick'] is not None:
            opt['brick'] = BrickCatalog.read_list(opt['brick'])
        if opt['list'] is not None:
            self = cls.from_list(opt['list'])
            return self[self.mask_cmdline({**opt,**{'list':None}})]

        kwargs_files = cls.kwargs_files_from_cmdline(opt)

        bricknames = opt['brick'] if opt['brick'] is not None else []
        return cls.from_brick_randoms_id(bricknames=bricknames,kwargs_files=kwargs_files,stages=opt['stages'])

    def mask_cmdline(self, opt):
        """
        Return mask corresponding to command-line arguments in ``opt``: 'brick', :meth:`~legacysim.survey.get_randoms_id.keys`, 'stages', 'list'.

        If an argument is not in opt or is ``None``, no mask is applied.

        Parameters
        ----------
        opt : argparse.Namespace, dict
            Holds command-line options.

        Returns
        -------
        mask : Bool ndarray
            Mask.
        """
        mask = self.trues()
        if opt.get('brick',None) is not None:
            mask &= np.isin(self.brickname,opt['brick'])
        for key in get_randoms_id.keys():
            if opt.get(key,None) is not None:
                mask &= np.any([self.get(key) == o for o in opt[key]],axis=0)
        if opt.get('stages',None) is not None:
            optstages = Stages(opt['stages'])
            indices = [istages for istages,stages in enumerate(self._list_stages) if any(stages.isin(optstages))]
            #optstages = ListStages(opt['stages'])
            #indices = [istages for istages,stages in enumerate(self._list_stages) if stages in optstages]
            mask &= np.isin(self.stagesid,indices)
        if opt.get('list',None) is not None:
            other = self.from_list(opt['list'])
            mask &= self.isin(other,ignore_stage_version=True)
        return mask

    @staticmethod
    def set_default_output_cmdline(opt):
        """
        Set default output command-line options. Change ``opt`` in-place.

        Parameters
        ----------
        opt : argparse.Namespace, dict
            Command-line options.
        """
        if isinstance(opt,dict):
            getopt = dict.get
            setopt = dict.__setitem__
        else:
            getopt = getattr
            setopt = setattr
        setopt(opt,'source',getopt(opt,'source','legacysim'))
        setopt(opt,'stages',getopt(opt,'stages',None))
        setopt(opt,'pickle_pat',getopt(opt,'pickle_pat',None))
        if getopt(opt,'filetype',None) is None:
            setopt(opt,'filetype','tractor' if getopt(opt,'stages') is None else 'pickle')

    @classmethod
    def from_output_cmdline(cls, opt, force_from_disk=False):
        """
        Initialize :class:`RunCatalog` from command-line arguments of :meth:`get_output_parser`.

        If all arguments of :meth:`get_output_parser` are provided, create instance folowing :meth:`from_input_cmdline`.
        If ``force_from_disk == True``, further restrict to those runs for which catalogs are written on disk
        (default file type is 'tractor' except if 'stages' is not ``None``, in which case default is 'pickle').

        Else, explore the **legacyipe** or **legacysim** (default 'source') file structure to fill in the other command-line arguments;
        and return new instance.

        Parameters
        ----------
        opt : argparse.Namespace, dict
            Holds options of :meth:`get_output_parser`.

        force_from_disk : bool, default=False
            If ``True`` limit run list to files that exist on disk.

        Returns
        -------
        self : RunCatalog
            New instance.
        """
        if isinstance(opt,dict):
            opt = dict(opt)
        else:
            opt = vars(opt)

        cls.set_default_output_cmdline(opt)

        for key in ['list','brick'] + get_randoms_id.keys():
            opt.setdefault(key,None)
        if (not force_from_disk)\
            and ((opt['list'] is not None)\
                or (opt['brick'] is not None) and all([opt[key] is not None for key in get_randoms_id.keys()])):
            return cls.from_input_cmdline(opt)

        self = cls()
        for field in self.fields:
            self.set(field,[])

        if opt['brick'] is not None:
            opt['brick'] = BrickCatalog.read_list(opt['brick'])
        elif opt['list'] is not None:
            opt['brick'] = self.from_list(opt['list']).unique('brickname',sort_index=True).brickname

        use_pickle_pat = opt['filetype'] == 'pickle' and opt['pickle_pat'] is not None

        def cleanup(pattern):
            # remove duplicates for re.match
            for field in self.fields:
                pat = '?P<%(field)s>' % {'field':field}
                pattern = pattern.replace(pat,'',pattern.count(pat)-1)
            return pattern

        if use_pickle_pat:
            template_search = opt['pickle_pat'].replace('%(ranid)s','*').replace('%%(stage)s','*')
            template_match = opt['pickle_pat'].replace('%(brick).3s','(.*?)') % dict(brick='(?P<brickname>.*?)',
                                                                                ranid=get_randoms_id.match_template()) % dict(stage='(?P<stagesid>.*?)')
            template_match = cleanup(template_match)
        else:
            template_search = find_file(base_dir=opt['output_dir'],filetype=opt['filetype'],brickname=None,
                                        source=opt['source'],stage='*',**{key:'*' for key in get_randoms_id.keys()})
            template_match = find_file(base_dir=opt['output_dir'],filetype=opt['filetype'],brickname=None,
                                        source=opt['source'],stage='(?P<stagesid>.*?)',**get_randoms_id.kwargs_match_template())
            template_match = template_match.replace('%(brick).3s','(.*?)') % dict(brick='(?P<brickname>.*?)')
            template_match = cleanup(template_match)

        def decode_output_fn(fullname):
            group = re.match(template_match,fullname).group
            toret = {**get_randoms_id.as_dict(),**{'stagesid':Stages.default()}}
            for field in self.fields:
                try:
                    toret[field] = group(field)
                except IndexError:
                    pass
            return toret

        if opt['brick'] is None:
            fns = glob.iglob(template_search % dict(brick='*'))
        else:
            fns = []
            for brickname in opt['brick']:
                fns.append(glob.iglob(template_search % dict(brick=brickname)))
            fns = itertools.chain(*fns) # chain iterators

        for fn in fns:
            decode = decode_output_fn(fn)
            for field in self.fields:
                if field in get_randoms_id.keys():
                    decode[field] = int(decode[field])
                self.get(field).append(decode[field])
        self.to_np_arrays()
        self._length = self.brickname.size
        if self._length == 0:
            return self
        # now group stages
        self = self.group_stages()
        # restrictions
        self = self[self.mask_cmdline(opt)]

        return self

    @property
    def fields(self):
        """Return fields."""
        return ['brickname'] + get_randoms_id.keys() + ['stagesid']

    def get_list_stages(self):
        """Return :attr:`_list_stages`."""
        return self._list_stages

    def append_stages(self, *args, **kwargs):
        """Shortcut for ``self._list_stages.append(*args,**kwargs)``."""
        return self._list_stages.append(*args,**kwargs)

    def group_stages(self, copy=False):
        """
        Start from catalog of (brickname x randoms id x stage), group rows with same (brickname x randoms id) together,
        stack their stages and add stages id in column ``stagesid``.

        List of stages :attr:`_list_stages` is cleared beforehand.

        Parameters
        ----------
        copy : bool, default=False
            Return copy?

        Returns
        -------
        runcat : RunCatalog
            Catalog in correct format (brickname x randoms id x stages id).
        """
        runcat = self.remove_duplicates(copy=copy)
        runcat.get_list_stages().clear()

        uniqid = runcat.uniqid(fields=[field for field in runcat.fields if field != 'stagesid'])
        stagesid_bak = runcat.stagesid
        runcat.stagesid = runcat.zeros(dtype='i4')
        for uid in uniqid:
            mask = uniqid == uid
            runcat.stagesid[mask] = runcat.append_stages(stagesid_bak[mask].tolist())

        return runcat.remove_duplicates(fields=[field for field in runcat.fields if field != 'stagesid'])

    def without_stage_versions(self, copy=False):
        """
        Return catalog without caring for stage versions.

        Namely, stages with same names but with different module versions are considered the same.
        Then, :attr:`_list_stages` is reduced to the unique stages, and column ``stagesid`` is updated.

        Parameters
        ----------
        copy : bool, default=False
            Return copy?

        Returns
        -------
        runcat : RunCatalog
            Catalog without stage versions.
        """
        if copy:
            runcat = self.copy()
        else:
            runcat = self
        list_stages,list_istages = runcat.get_list_stages().without_versions()
        stagesid_bak = runcat.stagesid.copy()
        for istages,new_istages in enumerate(list_istages):
            runcat.stagesid[stagesid_bak == istages] = new_istages
        runcat._list_stages = list_stages
        return runcat

    def isin(self, other, fields=None, ignore_stage_version=False):
        """
        Return mask selecting rows that are in ``other`` for ``fields``.

        Parameters
        ----------
        other : BaseCatalog
            Other catalog.

        fields : string, list, default=None
            Single field or list of fields. If ``None``, use all fields.

        ignore_stage_version : bool, default=False
            Ignore stage versions for comparison of field ``stagesid``.
            Only used if 'stagesid' is in ``fields``.

        Returns
        -------
        mask : bool ndarray
            Mask.

        Note
        ----
        For this comparison, the column ``stagesid`` of ``other`` is updated such that
        the mapping to stages in ``other`` :attr:`_list_stages` is the same as for ``self``.
        Neither ``other`` nor ``self`` is modified in this process.
        """
        if fields is None:
            fields = self.fields
        if 'stagesid' not in fields:
            return super(RunCatalog,self).isin(other,fields=fields)
        if ignore_stage_version:
            self = self.without_stage_versions(copy=True)
            other = other.without_stage_versions(copy=True)
        self_istages_for_other = self.get_list_stages().match(other.get_list_stages())[0]
        other_stagesid_bak = other.stagesid
        other.stagesid = other.stagesid.copy()
        for other_istages,self_istages in enumerate(self_istages_for_other):
            other.stagesid[other_stagesid_bak == other_istages] = self_istages
        mask = super(RunCatalog,self).isin(other,fields=fields)
        other.stagesid = other_stagesid_bak
        return mask

    @classmethod
    def from_brick_randoms_id(cls, bricknames=None, kwargs_files=None, stages=None):
        """
        Initialize :class:`RunCatalog` from a list of bricks, randoms file ids and stages id.

        Parameters
        ----------
        bricknames : list, string, default=None
            Single brick name or list of brick names.

        kwargs_files : dict, list, default=None
            Single or list of :class:`~legacysim.survey.get_randoms_id` dictionaries.
            A run (row) is created for each brick name and each of these dictionaries.

        stages : list, string, default=None
            Stages (same for each row of the output catalog).

        Returns
        -------
        self : RunCatalog
            New instance.
        """
        if bricknames is None: bricknames = []
        if kwargs_files is None: kwargs_files = {}
        if np.isscalar(bricknames): bricknames = [bricknames]
        if isinstance(kwargs_files,dict): kwargs_files = [kwargs_files]
        self = cls()
        stagesid = self.append_stages(stages)
        for field in self.fields: self.set(field,[])
        for brickname in bricknames:
            for kwargs_file in kwargs_files:
                kwargs_file = get_randoms_id.as_dict(**kwargs_file)
                tmp = {**locals(),**kwargs_file}
                for field in self.fields:
                    self.get(field).append(tmp[field])
        self.to_np_arrays()
        return self

    @classmethod
    def from_catalog(cls, cat, list_stages=None, stages=None):
        """
        Initialize :class:`RunCatalog` from a catalog.

        Parameters
        ----------
        cat : BaseCatalog
            Catalog containing ``brickname``, :meth:`~legacysim.survey.get_randoms_id.keys` and ``stagesid`` columns.

        list_stages : ListStages, default=None
            If ``None``, call :meth:`group_stages` on ``cat``.
            Else, simply set :attr:`_list_stages` to ``list_stages``, which should describe ``cat.stagesid``.

        stages : list, string, int, default=None
            Stages (same for each row of the output catalog).
            If not ``None``, supersedes ``cat`` field ``stagesid``.
            If ``list_stages`` is ``None`` and ``cat`` has no field ``stagesid``, defaults to :meth:`Stages.default()`.

        Returns
        -------
        self : RunCatalog
            New instance.
        """
        self = cls()

        def copy(fields):
            for field in fields:
                self.set(field,np.array(cat.get(field)))

        if list_stages is None and 'stagesid' not in cat.fields and stages is None:
            stages = Stages.default()
        if stages is not None:
            copy([field for field in self.fields if field != 'stagesid'])
            self.stagesid = self.full(stages)
        else:
            copy(self.fields)
        if list_stages is None:
            self = self.group_stages()
        else:
            self._list_stages = list_stages.copy()
        return self.remove_duplicates(copy=True)

    def append(self, other):
        """Append ``other`` rows to ``self``, taking care to update the column ``stagesid``."""
        other_stagesid_bak = other.stagesid
        other.stagesid = other.stagesid.copy()
        for istages,stages in enumerate(other.get_list_stages()):
            other.stagesid[other_stagesid_bak == istages] = self.append_stages(stages)
        super(RunCatalog,self).append(other)
        other.stagesid = other_stagesid_bak
        self.remove_duplicates(copy=False)

    def replace_randoms_id(self, copy=False, kwargs_files=None):
        """
        Replace randoms id by those in ``kwargs_files``.

        Parameters
        ----------
        copy : bool, default=False
            Return copy?

        kwargs_files : dict, list, default=None
            Single or list of :class:`~legacysim.survey.get_randoms_id` dictionaries.
            A run (row) is created for each brick name and each of these dictionaries.

        Returns
        -------
        runcat : RunCatalog
            New instance.
        """
        if kwargs_files is None: kwargs_files = {}
        if isinstance(kwargs_files,dict): kwargs_files = [kwargs_files]
        for i,kwargs_file in enumerate(kwargs_files):
            kwargs_files[i] = get_randoms_id.as_dict(**kwargs_file)
        runcat = self.remove_duplicates(fields='brickname',copy=copy)
        bak = {}
        for key in get_randoms_id.keys(): bak[key] = runcat.get(key).copy()
        #runcat.tile(len(kwargs_files),copy=False)
        #for key in get_randoms_id.keys():
        #    runcat.set(key,np.concatenate([np.full_like(bak[key],kwargs_file[key]) for kwargs_file in kwargs_files]))
        size = runcat.size
        runcat.repeat(len(kwargs_files),copy=False)
        for key in get_randoms_id.keys():
            runcat.set(key,np.tile([kwargs_file[key] for kwargs_file in kwargs_files],size))
        return runcat

    def __iter__(self):
        """Iterate through the different runs and attach ``kwargs_file`` and ``stages`` on the fly."""
        for run in super(RunCatalog,self).__iter__():
            run.kwargs_file = {key:run.get(key) for key in get_randoms_id.keys()}
            run.stages = self._list_stages[run.stagesid]
            yield run

    def iter_mask(self, cat, fields=None):
        """
        Yield boolean mask for the different runs in input catalog ``cat``.

        Parameters
        ----------
        cat : BaseCatalog
            Catalog to be iterated over.

        fields : string, list, default=None
            Single field or list of fields. If ``None``, use all fields in ``self`` which are also in ``cat``.
        """
        if fields is None:
            fields = [field for field in self.fields if field in cat.fields]
        if isinstance(fields,str):
            fields = [fields]
        uniques = self.remove_duplicates(fields=fields,copy=True)
        for run in uniques:
            yield np.all([cat.get(field) == run.get(field) for field in fields],axis=0)

    def iter_index(self, *args, **kwargs):
        """Yield indices for the different runs in input catalog ``cat`` (see :meth:`iter_mask`)."""
        for mask in self.iter_mask(*args,**kwargs):
            yield np.flatnonzero(mask)

    def count_runs(self, *args, **kwargs):
        """Return the number of runs in input catalog ``cat`` (see :meth:`iter_mask`)."""
        return sum(mask.any() for mask in self.iter_mask(*args,**kwargs))

    def update_stages(self, copy=False):
        """
        Remove stages indices of :attr:`_list_stages` which are not in ``stagesid``.

        Hence, modify column ``stagesid``.

        Parameters
        ----------
        copy : bool, default=False
            Return copy?

        Returns
        -------
        runcat : RunCatalog
            New instance.
        """
        if copy:
            runcat = self.copy()
        else:
            runcat = self
        list_stages_bak = runcat.get_list_stages().copy()
        stagesid_bak = runcat.stagesid.copy()
        runcat._list_stages.clear()
        for istages,stages in enumerate(list_stages_bak):
            if np.any(stagesid_bak == istages):
                runcat.stagesid[stagesid_bak == istages] = runcat.append_stages(stages)
        return runcat

    def check(self):
        """Raise ``ValueError`` if there are rows with same (brickname x randoms id) but different ``stagesid``."""
        index = self.unique(fields=[field for field in self.fields if field != 'stagesid'],return_unique=False,return_index=True)
        if not index.size == self.size:
            raise ValueError('Same runs with different stages')

    def write_list(self, fn):
        """
        Write run list to ``fn``.

        Parameters
        ----------
        fn : string
            Path to run list.
        """
        utils.mkdir(os.path.dirname(fn))
        runcat = self.remove_duplicates(copy=True).update_stages()
        runcat.check()
        logger.info('Writing %s to %s.',runcat.__class__.__name__,fn)
        with open(fn,'w') as file:
            for istages,stages in enumerate(runcat._list_stages):
                file.write('#stages%d = %s\n' % (istages,stages))
            for run in runcat:
                file.write('%s %s stages%d\n' % (run.brickname,get_randoms_id(**run.kwargs_file),run.stagesid))

    @classmethod
    def from_list(cls, fns):
        """
        Initialize :class:`RunCatalog` from run list(s) in ``fns``.

        Parameters
        ----------
        fns : list, string
            Path to run list. If multiple paths are provided, catalogs are appended (see :meth:`append`).

        Returns
        -------
        self : RunCatalog
            New instance corresponding to the input run list(s).

        Note
        ----
        Column ``stagesid`` can be modified, in particular if more than one run lists are provided.
        """
        self = 0
        if np.isscalar(fns):
            fns = [fns]
        for fn in fns:
            tmp = RunCatalog()
            for field in tmp.fields: tmp.set(field,[])
            with open(fn,'r') as file:
                for line in file:
                    match = re.match('#stages(?P<i>.*?) = (?P<s>.*?)$',line)
                    if match is not None:
                        stages = match.group('s')
                        istages = tmp.append_stages(Stages(stages))
                        i = int(match.group('i'))
                        if istages != i:
                            raise ValueError('Stage header is incorrect: stage ID (%d) does not match stage order (%d).' % (i,istages))
                    else:
                        brickname,ranid,stages = line.split()
                        tmp.get('brickname').append(brickname)
                        tmp.get('stagesid').append(int(re.match('stages(?P<s>.*?)$',stages).group('s')))
                        ranid = get_randoms_id.match(ranid)
                        for key in ranid:
                            tmp.get(key).append(ranid[key])
                tmp.to_np_arrays()
                tmp.remove_duplicates(copy=False).update_stages()
                try:
                    tmp.check()
                except ValueError:
                    raise ValueError('Issue with file %s' % fn)
            self += tmp
        return self
