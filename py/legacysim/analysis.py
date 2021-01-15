"""Convenient classes to perform **legacysim** analysis: image cutouts, catalog merging, catalog matching, computing time."""

import os
import logging

import numpy as np
from scipy import stats,special
from matplotlib import pyplot as plt
import fitsio

from .survey import find_file
from .catalog import SimCatalog, RunCatalog
from . import utils


logger = logging.getLogger('legacysim.analysis')


class BaseImage(object):
    """
    Dumb class to read, slice and plot an image.

    Attributes
    ----------
    img : ndarray
        Image (indexed by ``img[y,x]``), may be multi-dimensional.

    xmin : int, float
        x-coordinate of ``(0,0)`` corner.

    ymin : int, float
        y-coordinate of ``(0,0)`` corner.
    """

    def read_image(self, fn, fmt='jpeg', xmin=0, ymin=0, **kwargs):
        """
        Read image, either in 'jpeg' or 'fits' fmt and add :attr:`img` to ``self``.

        Parameters
        ----------
        fn : string
            Image filename.

        fmt : string, defaut='jpeg'
            Image format, 'jpeg' or 'fits'.
            If 'jpeg', ``self.img`` will have shape ``(H,W,3)``.
            If 'fits', ``self.img`` will have shape ``(H,W)``.

        xmin : int, float, default=0
            x-coordinate of ``(0,0)`` corner.

        ymin : int, float, default=0
            y-coordinate of ``(0,0)`` corner.

        kwargs : dict, default={}
            Arguments to be passed to :func:`pyplot.imread` or :func:`fitsio.read`.

        Note
        ----
        Inspired by https://github.com/legacysurvey/obiwan/blob/master/py/obiwan/qa/visual.py
        """
        if fmt in ['jpg','jpeg']:
            #import skimage.io
            #img = skimage.io.imread(fn)
            img = np.array(plt.imread(fn,**kwargs))
            for i in range(3):
                img[:,:,i] = np.rot90(img[:,:,i].T,1)
        elif fmt.startswith('fits'):
            img = fitsio.read(fn,**kwargs)
        else:
            raise ValueError('Unkown image format %s' % fmt)
        self.img = img
        self.xmin = xmin
        self.ymin = ymin

    def set_subimage(self, slicex=slice(0,None), slicey=slice(0,None)):
        """
        Slice image and update :attr:`xmin`, :attr:`ymin` accordingly.

        Slices should be zero-indexed, in the image coordinates
        (i.e. do not account for :attr:`xmin` and :attr:`ymin`).

        Parameters
        ----------
        slicex : slice
            Slice along x-axis (second axis of :attr:`img`).

        slicey : slice
            Slice along y-axis (first axis of :attr:`img`).
        """
        self.xmin = self.xmin + slicex.start
        self.ymin = self.ymin + slicey.start
        self.img = self.img[slicey,slicex]

    @property
    def shape(self):
        """
        Return image shape (H,W).

        If image does not exist, defaults to :attr:`_shape_default`.
        """
        if not hasattr(self,'img'): return self._shape_default
        return self.img.shape

    def isRGB(self):
        """Whether image is multi-dimensional."""
        return len(self.img.shape) == 3

    @utils.saveplot()
    def plot(self, ax, cmap='gray', vmin=None, vmax=None, kwargs_range=None):
        """
        Plot image.

        Parameters
        ----------
        ax : plt.axes
            Where to plot image.
            One can also provide figure file name ``fn``.
            See ``utils.saveplot``.

        cmap : string, plt.Colormap, default='gray'
            Color map for :func:`pyplot.imshow`, ignore in case of RGB(A) image.

        vmin : float, default=None
            Minimum value for ``cmap``.

        vmax : float, default=None
            Maximum value for ``cmap``.

        kwargs_range : dict, default=None
            If provided, provided to ``Binning`` to determine ``vmin`` and ``vmax``.
        """
        if kwargs_range is not None:
            vmin,vmax = Binning(samples=self.img.flatten(),nbins=1,**kwargs_range).range
        ax.imshow(self.img,interpolation='none',origin='lower',cmap=cmap,vmin=vmin,vmax=vmax)


class ImageAnalysis(BaseImage):
    """
    Extend :class:`BaseImage` with **legacysim**-related convenience functions.

    Attributes
    ----------
    _shape_default : tuple
        Default shape.

    base_dir : string
        See below.

    source : string
        See below.

    sources : SimCatalog
        Injected sources, see :meth:`read_sources`.
    """

    _shape_default = (3600,3600)

    def __init__(self, base_dir='.', brickname=None, kwargs_simid=None, source='legacysim'):
        """
        Set **legacysim** or **legacypipe** file structure.

        Parameters
        ----------
        base_dir : string, default='.'
            **legacysim** or **legacypipe** root file directory.

        brickname : string, default=None
            Brick name.

        kwargs_simid : dict, default=None
            :class:`~legacysim.survey.get_sim_id` dictionary with keys :meth:`~legacysim.survey.get_sim_id.keys`.

        source : string, default='legacysim'
            If 'legacysim', search for **legacysim** file names, else **legacypipe** file names.
        """
        self.base_dir = base_dir
        self.brickname = brickname
        self.kwargs_simid = kwargs_simid or {}
        self.source = source

    def read_image(self, filetype='image-jpeg', band=None):
        """
        Read **legacysim** image and add :attr:`~BaseImage.img` to ``self``.

        Parameters
        ----------
        filetype : string, default='image-jpeg'
            Image file type. See :meth:`legacypipe.survey.LegacySurveyData.find_file`.

        band : list, tuple, string, default=None
            Image band(s). Only used in case the image is in 'fits' format.
            In this case, if band is a list, should be of length 3 to build up a RGB image
            with :func:`legacypipe.survey.get_rgb`.
            If ``None``, defaults to ``['g','r','z']``.
            Else, only the image in the corresponding band is read.
        """
        fmt = 'jpeg' if 'jpeg' in filetype else 'fits'
        band = band or ['g','r','z']
        if fmt == 'fits' and not np.isscalar(band):
            assert len(band) == 3
            img = []
            for b in band:
                fn = find_file(base_dir=self.base_dir,filetype=filetype,brickname=self.brickname,source=self.source,band=b,**self.kwargs_simid)
                super(ImageAnalysis,self).read_image(fn=fn,fmt=fmt,xmin=0,ymin=0)
                img.append(self.img)
            self.img = np.moveaxis(img,0,-1)
            from legacypipe.survey import get_rgb
            self.img = get_rgb(self.img,bands=band)
        else:
            fn = find_file(self.base_dir,filetype,brickname=self.brickname,source='legacysim',band=band,**self.kwargs_simid)
            super(ImageAnalysis,self).read_image(fn=fn,fmt=fmt,xmin=0,ymin=0)

    def read_image_wcs(self, filetype='image', band='g', ext=1):
        """
        Read image wcs.

        Parameters
        ----------
        filetype : string, default='image-jpeg'
            File type to read wcs from. See :meth:`legacypipe.survey.LegacySurveyData.find_file`.

        band : string, default='g'
            Image band(s). Shoud not matter.

        ext : int, default=1
            FITS extension to read header from.

        Note
        ----
        Inspired by https://github.com/legacysurvey/legacypipe/blob/master/py/legacypipe/image.py
        """
        fn = find_file(base_dir=self.base_dir,filetype=filetype,brickname=self.brickname,source=self.source,band=band,**self.kwargs_simid)
        self.header = fitsio.read_header(fn,ext=ext)
        from astrometry.util.util import wcs_pv2sip_hdr
        stepsize = 0
        if min(self.shape[:2]) < 600:
            stepsize = min(self.shape[:2]) / 10.
        self.wcs = wcs_pv2sip_hdr(self.header, stepsize=stepsize)

    def read_sources(self, base_dir=None, filetype='injected', source='legacysim'):
        """
        Read sources in the image add :attr:`sources` to ``self``.

        Parameters
        ----------
        base_dir : string, defaut=None
            If not ``None``, supersedes :attr:`base_dir`.

        filetype : string, default='injected'
            File type of sources. See :func:`legacysim.survey.find_file`.

        source : string, default='legacysim'
            If 'legacysim', search for **legacysim** file name, else **legacypipe** file name.
            If not ``None``, supersedes :attr:`source`.
        """
        if base_dir is None: base_dir = self.base_dir
        if source is None: source = self.source
        self.sources_fn = find_file(base_dir=base_dir,filetype=filetype,brickname=self.brickname,source=source,**self.kwargs_simid)
        self.sources = SimCatalog(self.sources_fn)
        if hasattr(self.sources,'collided'):
            # Remove sources that were not injected
            self.sources = self.sources[~self.sources.collided]
        if hasattr(self,'wcs'):
            bx,by = self.wcs.radec2pixelxy(self.sources.ra,self.sources.dec)[1:]
            self.sources.bx = bx - 1
            self.sources.by = by - 1

    def suggest_zooms(self, boxsize_in_pixels=None, match_in_degree=0.1/3600, range_observed_injected_in_degree=(5./3600,30./3600)):
        """
        Suggest image cutouts around injected sources and within some distance to true sources.

        Parameters
        ----------
        boxsize_in_pixels : int, default=None
            Box size (pixel) around the injected source.
            If ``None``, defaults to image smaller side divided by 36.

        match_in_degree : float, default=0.1/3600
            Radius (degree) to match injected to output sources.

        range_observed_injected_in_degree : tuple, list, default=(5./3600,30./3600)
            Range (degree) around the injected source where to find a true source.

        Returns
        -------
        slices : list
            List of slice ``(slicex,slicey)``, to be passed to :meth:`set_subimage`.
        """
        fn = find_file(base_dir=self.base_dir,filetype='tractor',brickname=self.brickname,source=self.source,**self.kwargs_simid)
        tractor = SimCatalog(fn)
        index_sources,_,distance = self.sources.match_radec(tractor,radius_in_degree=range_observed_injected_in_degree[-1],nearest=False,return_distance=True)
        matched_sources = index_sources[distance<match_in_degree]
        mask_matched = np.isin(index_sources,matched_sources)
        if not mask_matched.any():
            raise ValueError('No match found between random and Tractor catalogs.')
        mask_inrange = mask_matched & (distance > range_observed_injected_in_degree[0]) #& (distance < range_observed_injected_in_degree[-1])
        if not mask_inrange.any():
            raise ValueError('No random/tractor pair found within range = %s, you should try larger range' % range_observed_injected_in_degree)
        index_sources = np.unique(index_sources[mask_inrange])
        if boxsize_in_pixels is None: boxsize_in_pixels = np.min(self.shape[:2])//36
        bx,by = np.rint(self.sources.bx[index_sources]).astype(int)-self.xmin,np.rint(self.sources.by[index_sources]).astype(int)-self.ymin
        halfsize = boxsize_in_pixels//2
        rangex = bx-halfsize,bx+boxsize_in_pixels-halfsize+1
        rangey = by-halfsize,by+boxsize_in_pixels-halfsize+1
        mask_boxsize = (rangex[0]>=0) & (rangex[-1]<=self.shape[1]) & (rangey[0]>=0) & (rangey[-1]<=self.shape[0])
        if not mask_boxsize.any():
            raise ValueError('Boxsize too large')
        rangex = tuple(r[mask_boxsize] for r in rangex)
        rangey = tuple(r[mask_boxsize] for r in rangey)
        slices = [(slice(rangex[0][i],rangex[1][i]),slice(rangey[0][i],rangey[1][i])) for i in range(mask_boxsize.sum())]
        return slices

    def plot_sources(self, ax, radius_in_pixel=3./0.262, dr=None, color='r'):
        """
        Plot circles around :attr:`sources`.

        Parameters
        ----------
        ax : plt.axes
            Where to plot sources.

        radius_in_pixel : float, default=3./0.262
            Radius (pixel) around sources.

        dr : float, default=None
            Circle width (pixel).
            If ``None``, defaults to ``radius_in_pixel/20``.

        color : string, default='r'
            Circle color.
        """
        from matplotlib.patches import Wedge
        from matplotlib.collections import PatchCollection
        if dr is None: dr = radius_in_pixel/20.
        patches = [Wedge((x-self.xmin,y-self.ymin),r=radius_in_pixel,theta1=0,theta2=360,width=dr) for x,y in zip(self.sources.bx,self.sources.by)]
        coll = PatchCollection(patches,color=color) #,alpha=1)
        ax.add_collection(coll)


class CatalogMerging(object):
    """
    Class to load, merge and save **legacyipe** and **legacysim** catalogs.

    Attributes
    ----------
    base_dir : string
        See below.

    runcat : RunCatalog
        See below.

    source : string
        See below.

    cats : dict
        Dictionary holding catalogs.

    cats_fn : dict
        Dictionary holdind catalog file names.

    cats_dir : string
        See below.

    save_fn : string
        See below.
    """

    def __init__(self, base_dir='.', runcat=None, bricknames=None, kwargs_simids=None, source='legacysim', cats_dir=None, save_fn=None):
        """
        Set **legacysim** or **legacypipe** file structure.

        Parameters
        ----------
        base_dir : string, default='.'
            **legacysim** (if ``source == 'legacysim'``) or legacypipe (if ``source == 'legacypipe'``) root file directory.

        runcat : RunCatalog, defaut=None
            Run catalog used to select files from **legacysim** or **legacypipe** data structure.
            If provided, supersedes ``bricknames`` and ``kwargs_simids``.

        bricknames : list, default=None
            List of brick names.

        kwargs_simids : dict, list, default=None
            Single or list of :class:`~legacysim.survey.get_sim_id` dictionaries with keys :meth:`~legacysim.survey.get_sim_id.keys`.

        source : string, default='legacysim'
            If 'legacysim', search for **legacysim** file names, else **legacypipe** file names.

        cats_dir : string, default=None
            Directory where to save merged catalogs.

        save_fn : string, default=None
            File name where to save ``self``.
        """
        bricknames = bricknames or []
        kwargs_simids = kwargs_simids or {}
        self.base_dir = base_dir
        if runcat is None:
            self.runcat = RunCatalog.from_brick_sim_id(bricknames=bricknames,kwargs_simids=kwargs_simids)
        else:
            self.runcat = runcat
        self.source = source
        self.cats = {}
        self.cats_fn = {}
        self.cats_dir = cats_dir
        self.save_fn = save_fn

    def get_key(self, filetype='tractor', source=None):
        """
        Return key to catalog in :attr:`cats`.

        Parameters
        ----------
        filetype : string, default=None
            Type of file.

        source : string, default=None
            If not ``None``, supersedes :attr:`self.source`.

        Returns
        -------
        key : string
            Key in :attr:`cats`.
        """
        if source is None: source = self.source
        return '%s_%s' % (source,filetype.replace('-','_'))

    def merge(self, filetype='tractor', base_dir=None, source=None, keep_columns=None, add=False, write=False, **kwargs_write):
        """
        Merge catalogs, return the result and add to ``self`` (``add == True``) and/or directly write on disk (``write == True``).

        Parameters
        ----------
        filetype : string, default='tractor'
            Type of file to merge.

        base_dir : string, default=None
            **legacysim** (if ``source == 'legacysim'``) or legacypipe (if ``source == 'legacypipe'``) root file directory.
            If not ``None``, supersedes :attr:`base_dir`.

        source : string, default=None
            If 'legacysim', search for an **legacysim** file name, else a **legacypipe** file name.
            If not ``None``, supersedes :attr:`source`.

        keep_columns : list, default=None
            Keep only these columns.

        add : bool, default=False
            Add merged catalog to ``self``.

        write : bool, default=False
            Write merged catalog to disk.

        kwargs_write : bool
            If ``write``, arguments to pick up catalog file name. See :meth:`set_cat_fn`.

        Returns
        -------
        cat : SimCatalog
            Merged catalog.
        """
        if base_dir is None: base_dir = self.base_dir
        if source is None: source = self.source

        cat = 0
        if (not write) and (not add):
            logger.warning('Nothing to be done with loaded files. Escaping.')
            return cat

        def read_catalog(fn,**kwargs):
            if os.path.isfile(fn):
                return SimCatalog(fn,**kwargs)
            logger.warning('File %s not found.',fn)
            return None

        for run in self.runcat:
            if filetype in ['ps','ps-events']:
                fn = find_file(base_dir=base_dir,filetype='ps',brickname=run.brickname,source='legacysim',**run.kwargs_simid)
                tmp = read_catalog(fn,ext=1)
                if tmp is None: continue
                tf = tmp.unixtime.max()
                events = read_catalog(fn,ext=2)
                ti = events.unixtime.min()
                if filetype == 'ps-events':
                    tmp = events
                else:
                    tmp.mid = tmp.full(tmp.get_header()['PPID'])
                tmp.unixti = tmp.full(ti)
                tmp.unixtf = tmp.full(tf)
                tmp.brickname = tmp.full(run.brickname)
            else:
                fn = find_file(base_dir=base_dir,filetype=filetype,brickname=run.brickname,source=source,**run.kwargs_simid)
                tmp = read_catalog(fn)
                if tmp is None: continue
            for key,val in run.kwargs_simid.items():
                tmp.set(key,tmp.full(val))
            if filetype == 'injected':
                tmp.cut(~tmp.collided)
            if keep_columns is not None:
                tmp.keep_columns(*keep_columns)
            cat += tmp
        key = self.get_key(filetype=filetype,source=source)
        if write:
            self.write_catalog(cat=cat,**kwargs_write)
        if add:
            self.cats[key] = cat
        return cat

    def set_cat_fn(self, cat_base=None, cat_fn=None, **kwargs_key):
        """
        Set catalog file name.

        Parameters
        ----------
        cat_base : string, default=None
            Catalog base name, added to :attr:`cats_dir`.

        cat_fn : string, default=None
            Catalog full name. If provided, supersedes ``cat_base``.

        kwargs_key : bool, default={}
            Arguments to :meth:`get_key`.

        Returns
        -------
        key : string
            Key to catalog file name in :attr:`cats_fn`.
        """
        key = self.get_key(**kwargs_key)
        if cat_fn is None:
            if cat_base is not None:
                cat_fn = os.path.join(self.cats_dir,cat_base)
        if cat_fn is not None:
            self.cats_fn[key] = cat_fn
        return key

    def write_catalog(self, cat=None, **kwargs):
        """
        Write catalog to disk.

        Parameters
        ----------
        cat : SimCatalog, default=None
            Catalog to save. If ``None``, is got from :attr:`cats`.

        kwargs : dict
            Arguments for :meth:`set_cat_fn`, to set catalog file name.
        """
        key = self.set_cat_fn(**kwargs)
        if cat is None: cat = self.cats[key]
        cat.writeto(self.cats_fn[key])

    def read_catalog(self, add=False, **kwargs):
        """
        Read catalog from disk.

        Parameters
        ----------
        add : bool, default=False
            Add catalog to ``self``.

        kwargs : dict
            Arguments for :meth:`set_cat_fn`, to set catalog file name.
        """
        key = self.set_cat_fn(**kwargs)
        cat = SimCatalog(self.cats_fn[key])
        if add: self.cats[key] = cat
        return cat

    def get(self, *args, **kwargs):
        """Return ``self`` attribute."""
        return getattr(self,*args,**kwargs)

    def set(self, *args, **kwargs):
        """Set ``self`` attribute."""
        return setattr(self,*args,**kwargs)

    def has(self, *args, **kwargs):
        """Has ``self`` this attribute?"""
        return hasattr(self,*args,**kwargs)

    def getstate(self):
        """Export ``self`` to ``dict``."""
        state = {}
        for key in ['base_dir','cats_fn','cats_dir']:
            state[key] = self.get(key)
        state['runcat'] = self.runcat.to_dict()
        return state

    def setstate(self, state):
        """Add ``state`` to ``self``."""
        self.cats = {}
        for key in state:
            self.set(key,state[key])
        self.runcat = RunCatalog.from_dict(self.runcat)

    def save(self, save_fn=None):
        """
        Save ``self`` to disk.

        Parameters
        ----------
        save_fn : string, default=None
            File name where to save ``self``.
            If not ``None``, supersedes :attr:`self.save_fn`.
        """
        if save_fn is not None: self.save_fn = save_fn
        logger.info('Saving %s to %s.',self.__class__.__name__,self.save_fn)
        utils.mkdir(os.path.dirname(self.save_fn))
        np.save(self.save_fn,self.getstate())

    @classmethod
    def load(cls, save_fn):
        """
        Load ``self`` from disk.

        Parameters
        ----------
        save_fn : string
            File name where ``self`` is saved.
        """
        state = np.load(save_fn,allow_pickle=True)[()]
        self = object.__new__(cls)
        self.setstate(state)
        return self

    def set_catalog(self, name, filetype=None, source=None, **kwargs_merge):
        """
        Convenience function to add catalog to ``self`` with name ``name``.

        First try to get it from :attr:`cats`.
        Else if the file name is specified in :attr:`cats_fn`, read the merged catalog from disk.
        Else merge catalogs.

        Parameters
        ----------
        name : string
            Name of the catalog to be added to ``self``.

        filetype : string, default=None
            Type of file to search for.

        source : string, default=None
            If not ``None``, supersedes :attr:`source`.

        kwargs_merge : dict
            Extra arguments for :meth:`merge`.
        """
        key = self.get_key(filetype=filetype,source=source)
        if key in self.cats:
            pass
        elif key in self.cats_fn:
            self.read_catalog(filetype=filetype,source=source,add=True)
        else:
            self.merge(filetype=filetype,source=source,add=True,**kwargs_merge)
        self.set(name,self.cats[key])


class CatalogMatching(CatalogMerging):
    """
    Extend :class:`CatalogMerging` with methods to match input and output catalogs.

    Attributes
    ----------
    input : SimCatalog
        Catalog of input sources.

    output : SimCatalog
        Catalog of output sources.
    """

    def getstate(self):
        """Export ``self`` to ``dict``."""
        state = super(CatalogMatching,self).getstate()
        for key in ['add_input_tractor','injected','observed','distance']:
            if self.has(key):
                state[key] = self.get(key)
        for put in ['input','output']:
            for template in ['inter_%s','extra_%s','inter_%s_injected']:
                key = template % put
                if self.has(key):
                    state[key] = self.get(key)
        return state

    def setstate(self, state):
        """Add ``state`` to ``self``."""
        super(CatalogMatching,self).setstate(state)
        if self.has('add_input_tractor'):
            self.setup(add_input_tractor=state['add_input_tractor'])

    def setup(self, add_input_tractor=False):
        """
        Add :attr:`input` and :attr:`output` **Tractor** catalog to ``self``.

        By default, only the sources injected by **legacysim** are considered for ``input``.
        These can be merged to the sources fitted by **legacypipe** by setting ``add_input_tractor``.

        Parameters
        ----------
        add_input_tractor : bool, string, default=False
            If ``True``, **legacypipe** **Tractor** catalogs are added to ``input``.
            In this case :attr:`~CatalogMerging.base_dir` is considered as the **legacyipe** root directory.
            If ``string``, specifies the path to the **legacyipe** root directory.

        """
        self.add_input_tractor = add_input_tractor
        self.set_catalog(name='input',filetype='injected',source='legacysim')
        self.set_catalog(name='output',filetype='tractor',source='legacysim')
        if add_input_tractor:
            kwargs = {}
            if isinstance(add_input_tractor,str): kwargs = {'base_dir':add_input_tractor}
            self.set_catalog(name='input_tractor',filetype='tractor',source='legacypipe',**kwargs)
        self.injected = self.input.index()
        self.observed = np.array([],dtype=int)
        if add_input_tractor:
            self.observed = np.arange(self.input.size,self.input.size+self.input_tractor.size)
            self.input.fill(self.input_tractor,index_self='after')

    def match(self, radius_in_degree=1.5/3600., add_input_tractor=False):
        """
        Match :attr:`input` to :attr:`output`.

        Parameters
        ----------
        radius_in_degree : float, default=1.5/3600.
            Radius (degree) for input - output matching.

        add_input_tractor : bool, string, default=False
            Passed on to :meth:`setup`.
        """
        self.setup(add_input_tractor=add_input_tractor)
        self.inter_input,self.inter_output,self.distance = [],[],[]
        index_input,index_output = self.input.index(),self.output.index()
        for mask_input,mask_output in zip(self.runcat.iter_mask(self.input),self.runcat.iter_mask(self.output)):
            mask_input[self.observed] = self.input.brickname[self.observed] == self.input.brickname[self.injected][0]
            inter_input,inter_output,distance = self.input[mask_input].match_radec(self.output[mask_output],nearest=True,
                                                                                    radius_in_degree=radius_in_degree,return_distance=True)
            self.inter_input.append(index_input[mask_input][inter_input])
            self.inter_output.append(index_output[mask_output][inter_output])
            self.distance.append(distance)
        for key in ['inter_input','inter_output','distance']:
            self.set(key,np.concatenate(self.get(key)))

        logger.info('Matching %d objects / %d in input, %d in output',self.inter_input.size,self.input.size,self.output.size)
        mask_injected = np.isin(self.inter_input,self.injected)
        for key in ['input','output']:
            self.set('extra_%s' % key,np.setdiff1d(self.get(key).index(),self.get('inter_%s' % key)))
            self.set('inter_%s_injected' % key,self.get('inter_%s' % key)[mask_injected])
        self.distance_injected = self.distance[mask_injected]
        logger.info('Matching %d injected objects / %d in input, %d in output',self.inter_input_injected.size,self.injected.size,self.output.size)

    def export(self, base='input', key_input='input', key_output=None, key_distance='distance', key_matched='matched', key_injected='injected',
                injected=False, write=False, **kwargs_write):
        """
        Export the matched catalog obtained with :meth:`match`.

        Parameters
        ----------
        base : string, default='input'
            Base for matched catalog. Can be:
            - 'input': output columns are added to input
            - 'output': input columns are added to output
            - 'inter': as 'input', but matched sources only are kept
            - 'extra': keep only sources which could not be matched, in either input or output
            - 'all': stack all sources in both input and output

        key_input : string, default='input'
            If not ``None``, prefix to add to input fields.

        key_output : string, default=None
            If not ``None``, prefix to add to output fields.

        key_distance : string, default='distance'
            If not ``None``, field to save angular distance between matched input and output sources.

        key_matched : string, default='matched'
            If not ``None``, field to save boolean mask identifying matched input and output sources.

        key_injected : string, default='injected'
            If not ``None``, field to save boolean mask identifying injected sources.

        injected : bool, default=False
            If ``True``, restrict to injected sources.

        write : bool, default=False
            Write catalog to disk.

        kwargs_write : dict
            Arguments for :meth:`write_catalog`.

        Returns
        -------
        cat : SimCatalog
            Catalog of input - output sources.
        """
        full_input = self.input.copy()
        if key_input:
            for field in full_input.fields: full_input.rename(field,'%s_%s' % (key_input,field))
        output = self.output.copy()
        if key_output:
            for field in output.fields: output.rename(field,'%s_%s' % (key_output,field))
        if key_distance is not None:
            for key,cat in zip(['input','output'],[full_input,output]):
                distance = cat.nans()
                distance[self.get('inter_%s' % key)] = self.distance
                cat.set(key_distance,distance)
        if key_matched is not None:
            for key,cat in zip(['input','output'],[full_input,output]):
                match = cat.falses()
                match[self.get('inter_%s' % key)] = True
                cat.set(key_matched,match)

        inter_input,inter_output = self.inter_input,self.inter_output
        extra_input,extra_output = self.extra_input,self.extra_output
        if injected:
            inter_input,inter_output = self.inter_input_injected,self.inter_output_injected
        if key_injected:
            mask_injected = full_input.falses()
            mask_injected[self.injected] = True
            full_input.set(key_injected,mask_injected)
        if base == 'input':
            cat = full_input
            cat.fill(output,index_self=inter_input,index_other=inter_output)
        elif base == 'output':
            cat = output
            cat.fill(full_input,index_self=inter_output,index_other=inter_input)
        elif base == 'inter':
            cat = full_input[inter_input]
            cat.fill(output,index_self=None,index_other=inter_output)
        elif base == 'extra':
            cat = full_input[extra_input]
            cat.fill(output,index_self='after',index_other=extra_output)
        elif base == 'all':
            cat = full_input[self.injected] if injected else full_input
            cat.fill(output,index_self='after')
        if write:
            self.write_catalog(cat=cat,filetype='match_%s' % base,source='legacysim',**kwargs_write)
        return cat

    @utils.saveplot()
    def plot_scatter(self, ax, field, injected=True, xlabel=None, ylabel=None,
                    square=False, regression=False, diagonal=False, label_entries=True,
                    kwargs_xlim=None, kwargs_ylim=None, kwargs_scatter=None, kwargs_regression=None, kwargs_diagonal=None):
        """
        Scatter plot :attr:`output` v.s. :attr:`input`.

        Parameters
        ----------
        ax : plt.axes
            Where to plot.

        field : string
            Name of catalog column to plot.

        injected : bool, default=True
            If ``True``, restrict to injected sources. Else all (actual and injected) sources are considered.

        xlabel : string, default=None
            x-label, if ``None``, defaults to ``'input_%s' % field``.

        ylabel : string, default=None
            y-label, if ``None``, defaults to ``'output_%s' % field``.

        square : bool, default=False
            If ``True``, enforce square plot.

        regression : bool, default=False
            If ``False``, plot regression line.

        diagonal : bool, default=False
            If ``False``, plot diagonal line.

        label_entries : bool, default=True
            If ``True``, add the number of entries to the plot.

        kwargs_xlim : dict, default=None
            Arguments for :class:`Binning`, to define the x-range.

        kwargs_ylim : dict, default=None
            Arguments for :class:`Binning`, to define the y-range.

        kwargs_scatter : dict, default=None
            Extra arguments for :func:`pyplot.scatter`.

        kwargs_regression : dict, default=None
            Extra arguments for :func:`pyplot.plot` regression line.

        kwargs_diagonal : dict, default=None
            Extra arguments for :func:`pyplot.plot` diagonal line.
        """
        kwargs_scatter = {**{'s':10,'marker':'.','alpha':1,'edgecolors':'none'},**(kwargs_scatter or {})}
        kwargs_regression = {**{'linestyle':'--','linewidth':2,'color':'r','label':''},**(kwargs_regression or {})}
        kwargs_diagonal = {**{'linestyle':'--','linewidth':2,'color':'k'},**(kwargs_diagonal or {})}
        label_regression = kwargs_regression.pop('label',None)

        if injected:
            inter_input,inter_output = self.inter_input_injected,self.inter_output_injected
        else:
            inter_input,inter_output = self.inter_input,self.inter_output

        values1 = self.input.get(field)[inter_input]
        values2 = self.output.get(field)[inter_output]

        if xlabel is None: xlabel = 'input_%s' % field
        if ylabel is None: ylabel = 'output_%s' % field

        if kwargs_xlim is not None:
            xlim = Binning(samples=values1,nbins=1,**kwargs_xlim).range
            ax.set_xlim(xlim)

        if kwargs_ylim is not None:
            ylim = Binning(samples=values2,nbins=1,**kwargs_ylim).range
            ax.set_ylim(ylim)

        ax.scatter(values1,values2,**kwargs_scatter)

        if square:
            xlim,ylim = ax.get_xlim(),ax.get_ylim()
            xylim = min(xlim[0],ylim[0]),max(xlim[1],ylim[1])
            ax.axis('square')
            ax.set_xlim(xylim)
            ax.set_ylim(xylim)

        xlim,ylim = [np.array(tmp) for tmp in [ax.get_xlim(),ax.get_ylim()]]
        try:
            a,b = np.polyfit(values1,values2,1)
        except np.linalg.LinAlgError:
            raise np.linalg.LinAlgError('Regression failed, %s x-range = %.3f - %.3f, y-range = %.3f - %.3f'
                                        % (field,values1.min(),values1.max(),values2.min(),values2.max()))
        y = a*xlim + b
        r = np.corrcoef(values1,values2)[0,1]

        label_regression_ = label_regression
        if label_regression_ is not None:
            label_regression = '$\\rho = %.3f$' % r
            if label_regression_:
                label_regression = '%s %s' % (label_regression_,label_regression)
        else: label_regression = None

        if regression:
            ax.plot(xlim,y,label=label_regression_,**kwargs_regression)
            ax.set_ylim(ylim)
        elif label_regression:
            ax.text(0.95,0.05,label_regression,horizontalalignment='right',verticalalignment='bottom',transform=ax.transAxes,color='k')
        if diagonal:
            ax.plot(xlim,xlim,**kwargs_diagonal)
            ax.set_ylim(ylim)
        if label_entries:
            label = '%d entries' % len(values1)
            ax.text(0.05,0.95,label,horizontalalignment='left',verticalalignment='top',transform=ax.transAxes,color='k')
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

    @utils.saveplot()
    def plot_hist(self, ax, field, injected=True, xlabel=None, ylabel=None, divide_uncer=True,
                label_entries=True, label_mean_std=True, kwargs_xedges=None, kwargs_hist=None):
        """
        Histogram of :attr:`output` v.s. :attr:`input` differences.

        Parameters
        ----------
        ax : plt.axes
            Where to plot.

        field : string
            Name of catalog column to plot.

        injected : bool, default=True
            If ``True``, restrict to injected sources. Else all (actual and injected) sources are considered.

        xlabel : string, default=None
            x-label, if ``None``, defaults to ``'input_%s' % field``.

        ylabel : string, default=None
            y-label, if ``None``, defaults to ``'output_%s' % field``.

        divide_uncer : bool, default=True
            If ``True``, divide the difference ``output - input`` by the estimated uncertainty.

        label_entries : bool, default=True
            If ``True``, add the number of entries to the plot.

        label_mean_std : bool, default=True
            If ``True``, add the estimated mean, median, standard deviation to the plot.

        kwargs_xedges : dict, default=None
            Arguments for :class:`Binning`, to define the x-edges.

        kwargs_hist : dict, default=None
            Extra arguments for :func:`pyplot.hist`.
        """
        kwargs_xedges = kwargs_xedges or {}
        kwargs_hist = {**{'histtype':'step','color':'k'},**(kwargs_hist or {})}

        if injected:
            inter_input,inter_output = self.inter_input_injected,self.inter_output_injected
        else:
            inter_input,inter_output = self.inter_input,self.inter_output
        values = self.output.get(field)[inter_output]-self.input.get(field)[inter_input]
        if divide_uncer:
            if 'flux' in field: field_ivar = field.replace('flux','flux_ivar')
            else: field_ivar = '%s_ivar' % field
            ivar = self.output.get(field_ivar)[inter_output]
            values = values*np.sqrt(ivar)
        if xlabel is None:
            xlabel = '\\Delta \\mathrm{%s}' % field.replace('_','\_')
            if divide_uncer: xlabel = '$%s \\times \\sqrt{\\mathrm{%s}}$' % (xlabel,field_ivar.replace('_','\_'))
            else: xlabel = '$%s$' % xlabel

        edges = Binning(samples=values,**kwargs_xedges).edges
        ax.hist(values,bins=edges,**kwargs_hist)
        ax.set_xlabel(xlabel)
        if ylabel is not None: ax.set_ylabel(ylabel)
        if label_entries:
            label = '%d entries' % len(values)
            ax.text(0.05,0.95,label,horizontalalignment='left',verticalalignment='top',transform=ax.transAxes,color='k')
        if label_mean_std:
            label = '$\mathrm{median} = %.2g$\n' % np.median(values)
            label += '$\mathrm{mean} = %.2g$\n' % np.mean(values)
            label +='$\mathrm{std} = %.2g$\n' % np.std(values,ddof=1)
            label +='$\mathrm{std(med)} = %.2g$' % estimate_std_outliers(values)
            ax.text(0.95,0.95,label,horizontalalignment='right',verticalalignment='top',transform=ax.transAxes,color='k')


class ResourceEventAnalysis(CatalogMerging):
    """
    Extend :class:`CatalogMerging` with methods to analyze computing time based on events saved in ``ps`` files.

    Attributes
    ----------
    _sorted_events : list
        Events sorted by chronological order.

    events : SimCatalog
        Concatenated events read from ``ps`` files.
    """

    _sorted_events = ['start', 'stage_tims: starting', 'stage_tims: starting calibs', 'stage_tims: starting read_tims', 'stage_tims: done read_tims',
        'stage_refs: starting', 'stage_outliers: starting', 'stage_halos: starting', 'stage_image_coadds: starting',
        'stage_srcs: starting', 'stage_srcs: detection maps', 'stage_srcs: sources', 'stage_srcs: SED-matched', 'stage_fitblobs: starting',
        'stage_coadds: starting', 'stage_coadds: model images', 'stage_coadds: coadds', 'stage_coadds: extras',
        'stage_wise_forced: starting', 'stage_wise_forced: photometry', 'stage_wise_forced: results',
        'stage_galex_forced: starting', 'stage_galex_forced: photometry', 'stage_galex_forced: results',
        'stage_writecat: starting', 'stage_writecat: done']

    def process_events(self, events=None, time='reltime', statistic='mean'):
        """
        Return statistics about event durations.
        Assumes event are recorded at the beginning of the corresponding step.

        Parameters
        ----------
        events : array-like, string, default=None
            List of events to get statistics from, e.g. ``['stage_halos: starting']``.
            See ``self._sorted_events``.
            If ``None``, consider all events.
            If ``stage``, consider only starting stage events ``('stage_xxx: starting')``.

        time : string, default='reltime'
            Time to consider for calculation.
            If 'reltime', consider the time at which events happens relative to the beginning of the run.
            Else, if 'steptime', consider the time duration of each event, i.e. the time difference between events,
            starting from the last time step registered for the run.

        statistic : string, callable, default='mean'
            Statistic to compute from event time, passed on to :func:`scipy.stats.binned_statistic`.

        Returns
        -------
        events, values : ndarray
            Events and corresponding statistic.
        """
        self.set_catalog(name='events',filetype='ps-events')

        def get_sorted_events():
            sorted_events = np.array(self._sorted_events)
            return sorted_events[np.isin(sorted_events,self.events.event)]

        if events is None:
            events = get_sorted_events()
        elif isinstance(events,str) and events == 'stage':
            uniques = get_sorted_events()
            base = uniques[0].split(':')[0]
            events_sel = [uniques[0]]
            for event in uniques:
                if event.startswith(base): continue
                base = event.split(':')[0]
                events_sel.append(event)
            events = np.asarray(events_sel)
        if time == 'reltime':
            indices = self.events.event
            values = self.events.unixtime - self.events.unixti
        elif time == 'steptime':
            indices = self.events.event
            values = self.events.nans()
            for mask in self.runcat.iter_mask(self.events):
                events_run = self.events[mask]
                dt = np.zeros(events_run.size,dtype='f4')
                tf = events_run.unixtf[0]
                for event in events[::-1]:
                    mask_event = events_run.event == event
                    if mask_event.any():
                        tmp = events_run.unixtime[mask_event]
                        dt[mask_event] = tf - tmp
                        tf = tmp[0]
                values[mask] = dt
        else:
            raise ValueError('Unknown requested time %s' % time)

        uniques,indices,inverses = np.unique(indices,return_index=True,return_inverse=True)
        uniqid = np.arange(len(uniques))
        edges = np.concatenate([uniqid,[uniqid[-1]+1]])
        values = stats.binned_statistic(uniqid[inverses],values,statistic=statistic,bins=edges)[0]
        values = values[np.searchsorted(uniques,events)]

        return events,values

    def plot_bar(self, ax, events='stage', label_entries=True, kwargs_bar=None):
        """
        Plot event mean and standard deviation in the form of a bar graph.

        Parameters
        ----------
        ax : plt.axes
            Where to plot image.
            One can also provide figure file name ``fn``.
            See :func:`legacysim.utils.saveplot`.

        events : array-like, string, default=None
            Passed on to :meth:`process_events`.

        label_entries : bool, default=True
            If ``True``, add the number of entries to the plot.

        kwargs_bar : dict, default=None
            Extra arguments for :func:`pyplot.bar`.
        """
        kwargs_bar = {**{'align':'center','alpha':0.5,'ecolor':'black','capsize':2},**(kwargs_bar or {})}
        names,mean = self.process_events(events=events,time='steptime',statistic='mean')
        std = self.process_events(events=names,time='steptime',statistic='std')[1]
        labels = []
        for name in names:
            label = name
            if events in ['start']: label = name.split(':')[0]
            labels.append(label.replace('stage_',''))
        labels = np.array(labels)
        ax.yaxis.grid(True)
        ax.bar(labels,mean,yerr=std,**kwargs_bar)
        ax.set_xticklabels(labels=labels,rotation=40,ha='right')
        ax.set_ylabel('Average wall time [s]')
        if label_entries:
            label = '%d entries' % self.runcat.count_runs(self.events)
            ax.text(0.05,0.95,label,horizontalalignment='left',verticalalignment='top',transform=ax.transAxes,color='k')


class ResourceAnalysis(ResourceEventAnalysis):
    """
    Extend events-only analyzes of :class:`ResourceEventAnalysis` with analysis of full time series saved in ``ps`` files.

    Attributes
    ----------
    series : SimCatalog
        Concatenated time series read from ``ps`` files.
    """

    @staticmethod
    def process_one_series(series, quantities=None):
        """
        Compute resources for a single time series, split between the following categories:
        'ps' (the process running `ps`), 'main' (the master process),
        'workers' (non-zero in case of multithreading), 'others' (other processes).

        Parameters
        ----------
        series : SimCatalog
            Time series to analyze.

        quantities : list, default=None
            Quantities to analyze.
            If ``None``, defaults to ``['proc_icpu','vsz']``.

        Returns
        -------
        stats : dict
            A dictionary holding time series for each quantity and process category.
        """
        quantities = quantities or ['proc_icpu','vsz']

        steps,index_steps = np.unique(series.step, return_index=True)
        map_steps = np.zeros(steps.max()+1,dtype='i4')
        map_steps[steps] = np.arange(len(steps))
        reltime = series.unixtime[index_steps] - series.unixti[index_steps]
        mid = series.mid[0]

        stats = {'time':reltime}
        for q in quantities:
            stats[q] = {}
            stats[q]['ps'] = np.zeros(len(steps),dtype='f4')
            stats[q]['others'] = np.zeros(len(steps),dtype='f4')
            stats[q]['main'] = np.zeros(len(steps),dtype='f4')
            stats[q]['workers'] = []

        mask_main = series.pid == mid
        mask_mine = mask_main | (series.ppid == mid)
        pids = np.unique(series.pid[mask_mine])

        for pid in pids:
            index_pid = np.flatnonzero(series.pid == pid)
            step_pid = map_steps[series.step[index_pid]]
            cmds = np.unique(series.command[index_pid])
            if len(cmds) == 1 and cmds[0].startswith('ps ax'):
                for q in quantities:
                    stats[q]['ps'][step_pid] += series.get(q)[index_pid]
            else:
                for q in quantities:
                    tmp = np.zeros(len(steps),dtype='f4')
                    tmp[step_pid] = series.get(q)[index_pid]
                    if pid == mid: stats[q]['main'] = tmp
                    else: stats[q]['workers'].append(tmp)
        for q in quantities: stats[q]['workers'] = np.array(stats[q]['workers'])

        pids = np.unique(series.pid[~mask_mine])
        for pid in pids:
            index_pid = np.flatnonzero(series.pid == pid)
            step_pid = map_steps[series.step[index_pid]]
            for q in quantities:
                stats[q]['others'][step_pid] += series.get(q)[index_pid]

        return stats

    def process_all_series(self, quantities=None):
        """
        Compute average resources for all time series, split between the following categories:
        'ps' (the process running `ps`), 'main' (the master process),
        'workers' (non-zero in case of multithreading), 'others' (other processes).

        Parameters
        ----------
        quantities : list, default=None
            Quantities to analyze.
            If ``None``, defaults to ``['proc_icpu','vsz']``.

        Returns
        -------
        stats : dict
            A dictionary holding summary time series for each quantity and process category.
        """
        quantities = quantities or ['proc_icpu','vsz']

        self.set_catalog(name='series',filetype='ps')
        stats = {q:{} for q in quantities}
        stats['time'] = []
        for mask in self.runcat.iter_mask(self.series):
            series = self.series[mask]
            qseries = self.process_one_series(series,quantities=quantities)
            for q in quantities:
                for key,val in qseries[q].items():
                    if key not in stats[q]: stats[q][key] = []
                    if key == 'workers':
                        val = val.max(axis=0)
                    stats[q][key].append(val)
            stats['time'].append(qseries['time'])
        time_range = (0.,max(time.max() for time in stats['time']))
        num = max(len(time) for time in stats['time'])
        time = np.linspace(*time_range,num=num)
        for q in quantities:
            for key,val in stats[q].items():
                stats[q][key] = np.mean([np.interp(time,t,v) for t,v in zip(stats['time'],val)],axis=0)
        stats['time'] = time
        return stats

    def add_event_vlines(self, ax, events=None):
        """
        Plot vertical lines to indicate start of events.

        Parameters
        ----------
        ax : plt.axes
            Where to plot events.

        events : array-like, string, default=None
            Passed on to :meth:`~ResourceEventAnalysis.process_events`.
        """
        names,times = self.process_events(events=events)
        for ievent,(name,time) in enumerate(zip(names,times)):
            ax.axvline(time,color='k',alpha=0.1)
            label = name
            if events == 'stage': label = name.split(':')[0]
            label = label.replace('stage_','')
            ycoord = [0.05,0.35,0.65][ievent % 3]
            ax.text(time,ycoord,label,rotation='vertical',horizontalalignment='left',
                    verticalalignment='bottom',transform=ax.get_xaxis_transform(),color='k')

    @utils.saveplot()
    def plot_one_series(self, ax, series=None, events='stage', processes=None, kwargs_fig=None, kwargs_plot=None):
        """
        Plot resources for a single time series.

        Parameters
        ----------
        ax : plt.axes
            Where to plot the time series.
            One can also provide figure file name ``fn``.
            See :func:`legacysim.utils.saveplot`.

        series : SimCatalog, default=None
            Time series to analyze.
            If ``None``, defaults to :attr:`series`.

        events : array-like, string, default='stage'
            Passed on to :meth:`~ResourceEventAnalysis.process_events`.

        processes : list, default=None
            Processes to plot.
            If ``None``, defaults to ``['main','workers']``.
            If 'all', plot all processes of :meth:`process_one_series`.

        kwargs_fig : dict, default=None
            Extra arguments for :func:`pyplot.savefig`.
            See :func:`legacysim.utils.saveplot`.

        kwargs_plot : dict, default=None
            Extra arguments for :func:`pyplot.plot`.
        """
        processes = processes or ['main','workers']
        kwargs_fig = {**{'figsize':(10,5)},**(kwargs_fig or {})}
        kwargs_plot = kwargs_plot or {}

        if series is None:
            self.set_catalog(name='series',filetype='ps')
            series = self.series
        series = self.process_one_series(series=series,quantities=['proc_icpu','vsz'])
        if processes == 'all':
            processes = list(series['proc_icpu'].keys())
        colors = kwargs_plot.pop('colors',plt.rcParams['axes.prop_cycle'].by_key()['color'])
        alpha = kwargs_plot.pop('alpha',1.)
        ax2 = ax.twinx()
        for key,color in zip(processes,colors):
            if key in ['workers']:
                alpha_ = 0.25*alpha
                cpu,vsz = series['proc_icpu'][key],series['vsz'][key]
            else:
                alpha_ = alpha
                cpu,vsz = [series['proc_icpu'][key]],[series['vsz'][key]]
            for iwork,(cpu_,vsz_) in enumerate(zip(cpu,vsz)):
                ax.plot(series['time'],cpu_,label=key if iwork==0 else None,color=color,alpha=alpha_,**kwargs_plot)
                ax2.plot(series['time'],vsz_/1e6,color=color,alpha=alpha_,linestyle='--',**kwargs_plot)
        ax.set_xlabel('Wall time [s]')
        ax.set_ylabel('Proc [%]')
        ax2.set_ylabel('VSS [GB]')
        self.add_event_vlines(ax,events=events)
        ax.legend()

    @utils.saveplot()
    def plot_all_series(self, ax, events='stage', processes=None, label_entries=True, kwargs_plot=None):
        """
        Plot summary resources for all time series.

        Parameters
        ----------
        ax : plt.axes
            Where to plot the time series.
            One can also provide figure file name ``fn``.
            See :func:`legacysim.utils.saveplot`.

        events : array-like, string, default='stage'
            Passed on to :meth:`~ResourceEventAnalysis.process_events`.

        processes : list, default=None
            Processes to plot.
            If ``None``, defaults to ``['main','workers']``.
            If 'all', plot all processes of :meth:`process_one_series`.

        label_entries : bool, default=True
            If ``True``, add number of entries to plot.

        kwargs_plot : dict, default=None
            Extra arguments for :func:`pyplot.plot`.
        """
        processes = processes or ['main','workers']
        kwargs_plot = kwargs_plot or {}

        series = self.process_all_series(quantities=['proc_icpu','vsz'])
        if processes == 'all':
            processes = list(series['proc_icpu'].keys())
        colors = kwargs_plot.pop('colors',plt.rcParams['axes.prop_cycle'].by_key()['color'])
        ax2 = ax.twinx()
        for key,color in zip(processes,colors):
            ax.plot(series['time'],series['proc_icpu'][key],label=key,color=color,**kwargs_plot)
            ax2.plot(series['time'],series['vsz'][key]/1e6,color=color,linestyle='--',**kwargs_plot)
        ax.set_xlabel('Wall time [s]')
        ax.set_ylabel('Proc [%]')
        ax2.set_ylabel('VSS [GB]')
        self.add_event_vlines(ax,events=events)
        ax.legend()
        if label_entries:
            label = '%d entries' % self.runcat.count_runs(self.events)
            ax.text(0.05,0.95,label,horizontalalignment='left',verticalalignment='top',transform=ax.transAxes,color='k')

# Utilities
class Binning(object):
    """
    Create edges to bin samples.

    Attributes
    ----------
    edges : ndarray
        Edges to bin samples.
    """

    def __init__(self, samples=None, weights=None, edges=None, nbins=10, range=None, quantiles=None, scale='linear'):
        """
        First set the total range, then the number of bins with :func:`numpy.histogram_bin_edges`.

        Parameters
        ----------
        samples : array-like
            Samples to be binned.

        weights : array-like, default=None
            Weights associated to ``samples``, used by :func:`numpy.histogram_bin_edges`.
            If ``None``, defaults to 1.

        edges : array-like, default=None
            If edges already provided, nothing to do!

        nbins : int, string, default=None
            Number of bins.
            If ``int``, used to define ``edges`` using ``scale``.
            Else, passed on to :func:`numpy.histogram_bin_edges`.

        range : array-like, default=None
            Range, i.e. ``edges`` minimum and maximum boundaries. If not ``None``, supersedes ``quantiles``.

        quantiles : array-like, default=None
            Quantiles (low,up) to define ``range``.
            If ``None``, set ``range`` to ``samples`` minimum and maximum.

        scale : string, default='linear'
            Used if ``nbins`` is ``int``.
            If 'linear', use a linear binning.
            If 'log', use a logarithmic binning.
        """
        self.edges = edges
        if edges is None:
            if range is None:
                if quantiles is None:
                    range = [samples.min(axis=-1),samples.max(axis=-1)]
                    range[-1] = range[-1]+(range[-1]-range[0])*1e-5
                else:
                    range = np.percentile(samples,q=np.array(quantiles)*100.,axis=-1).T
            if range[0] is None: range[0] = samples.min(-1)
            if range[-1] is None:
                range[-1] = samples.max(-1)
                range[-1] = range[-1]+(range[-1]-range[0])*1e-5
            if isinstance(nbins,np.integer):
                if scale == 'linear':
                    self.edges = np.linspace(range[0],range[-1],nbins+1)
                elif scale == 'log':
                    self.edges = np.logspace(np.log10(range[0]),np.log10(range[-1]),nbins+1,base=10)
                else:
                    raise ValueError('Scale %s is unkown.' % scale)
            else:
                self.edges = np.histogram_bin_edges(samples,bins=nbins,range=range,weights=weights)

    @property
    def range(self):
        """Return ``edges`` minimum and maximum boundaries."""
        return (self.edges[0],self.edges[-1])

    @property
    def nbins(self):
        """Return number of bins."""
        return len(self.edges)-1

    @property
    def centers(self):
        """Return bin centers."""
        return (self.edges[:-1]+self.edges[1:])/2.


def estimate_std_outliers(samples):
    """
    Estimate the standard deviation of ``samples`` from the median of the folded distribution.

    Less sensitive to outliers than standard deviation.
    """
    return np.median(np.abs(samples-np.median(samples)))/(2.**0.5*special.erfinv(1./2.))
