"""Convenient functions to handle **legacysim** inputs/outputs."""

import os
import sys
import logging
import functools

import numpy as np
from matplotlib import pyplot as plt
from astrometry.libkd import spherematch


logger = logging.getLogger('legacysim.utils')


def setup_logging(level=logging.INFO, stream=sys.stdout, filename=None, filemode='w', **kwargs):
    """
    Set up logging.

    Parameters
    ----------
    level : string, int, default=logging.INFO
        Logging level.

    stream : _io.TextIOWrapper, default=sys.stdout
        Where to stream.

    filename : string, default=None
        If not ``None`` stream to file name.

    filemode : string, default='w'
        Mode to open file, only used if filename is not ``None``.

    kwargs : dict
        Other arguments for :func:`logging.basicConfig`.
    """
    # Cannot provide stream and filename kwargs at the same time to logging.basicConfig, so handle different cases
    # Thanks to https://stackoverflow.com/questions/30861524/logging-basicconfig-not-creating-log-file-when-i-run-in-pycharm
    if isinstance(level,str):
        level = {'info':logging.INFO,'debug':logging.DEBUG,'warning':logging.WARNING}[level]
    for handler in logging.root.handlers:
        logging.root.removeHandler(handler)
    fmt = logging.Formatter(fmt='%(asctime)s %(name)-15s %(levelname)-8s %(message)s',datefmt='%m-%d %H:%M ')
    if filename is not None:
        mkdir(os.path.dirname(filename))
        handler = logging.FileHandler(filename,mode=filemode)
    else:
        handler = logging.StreamHandler(stream=stream)
    handler.setFormatter(fmt)
    logging.basicConfig(level=level,handlers=[handler],**kwargs)


class MonkeyPatching(object):
    """
    Class to add attributes to modules, e.g.::

        import module
        with MonkeyPatching() as mp:
            mp.add(module,'function',fun)
            # module.function is fun
        # module.function is original function if exists

    Attributes
    ----------
    _old : dict
        Dictionary holding original attributes.

    _new : dict
        Dictionary holding new (temporary) attributes.
    """

    def __init__(self):
        """Create internal dictionaries :attr:_old and :attr:_new."""
        self._old = {}
        self._new = {}

    def __enter__(self):
        """Return self."""
        return self

    def __contains__(self,item):
        """Return whether the tuple ``(module,name) = item`` has been registered."""
        return self._new.__contains__(item)

    def __iter__(self):
        """Iterate through (module,name) tuples."""
        return self._new.__iter__()

    def keys(self):
        """Return (module,name) keys."""
        return self._new.keys()

    def add(self, mod, name, attr):
        """Add attribute ``attr`` with name ``name`` to module ``mod`` (and save ``mod.name`` if already exists)."""
        if hasattr(mod,name):
            self._old[(mod,name)] = getattr(mod,name)
        self._new[(mod,name)] = attr
        setattr(mod,name,attr)

    def remove(self, mod, name):
        """Remove added tie of ``name`` to module ``mod`` and restores the old one if exists."""
        if (mod,name) not in self:
            raise KeyError('No attribute %s found in module %s' % (name,mod))
        del self._new[(mod,name)]
        if (mod,name) in self._old:
            setattr(mod,name,self._old[(mod,name)])
            del self._old[(mod,name)]
        else:
            delattr(mod,name)

    def clear(self):
        """Remove all added (module,name) ties."""
        for mod,name in list(self.keys()):
            self.remove(mod,name)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Clean up everything."""
        self.clear()


def saveplot(giveax=True):
    """
    Decorate plotting methods, to achieve the following behaviour for the decorated method:

    If ``ax`` is provided, add image to ``ax``.
    Else, if ``fn`` is provided, save image to ``fn``, with arguments ``kwargs_fig``.
    Else, show image.

    Parameters
    ----------
    giveax : bool, default=True
        If ``True``, provide ``ax`` to decorated method.
        Else, ``ax`` is not provided.
    """
    def decorator(func):

        @functools.wraps(func)
        def wrapper(self,ax=None,fn=None,kwargs_fig=None,**kwargs):
            isax = True
            if giveax:
                if ax is None:
                    isax = False
                    ax = plt.gca()
                func(self,ax,**kwargs)
            else:
                isax = False
                func(self,**kwargs)
                if ax is None:
                    ax = plt.gca()
            if fn is not None:
                kwargs_fig = kwargs_fig or {}
                savefig(fn,**kwargs_fig)
            elif not isax:
                plt.show()
            return ax
        return wrapper

    return decorator


def savefig(fn, bbox_inches='tight', pad_inches=0.1, dpi=200, **kwargs):
    """Save matplotlib figure to ``fn``."""
    mkdir(os.path.dirname(fn))
    logger.info('Saving figure to %s.',fn)
    plt.savefig(fn,bbox_inches=bbox_inches,pad_inches=pad_inches,dpi=dpi,**kwargs)
    plt.close(plt.gcf())


def mkdir(dirnm):
    """Try to create ``dirnm`` and catch :class:`OSError`."""
    try:
        os.makedirs(dirnm) #MPI...
    except OSError:
        return


def get_parser_args(args=None):
    """
    Transform args (``None``, ``str``, ``list``, ``dict``) to parser-compatible (list of strings) args.

    Parameters
    ----------
    args : string, list, dict, default=None
        Arguments. If dict, '--' are added in front and there should not be positional arguments.

    Returns
    -------
    args : None, list of strings.
        Parser arguments.

    Notes
    -----
    All non-strings are converted to strings with :func:`str`.
    """
    if isinstance(args,str):
        return args.split()

    if isinstance(args,list):
        return list(map(str,args))

    if isinstance(args,dict):
        toret = []
        for key in args:
            toret += ['--%s' % key]
            if isinstance(args[key],list):
                toret += [str(arg) for arg in args[key]]
            else:
                val = str(args[key])
                if val: toret += [val]
        return toret

    return args


def list_parser_dest(parser, exclude=('help',)):
    """
    Return parser list of ``dest``.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        Parser.

    exclude : list, tuple, default=('help',)
        Brick name.

    Returns
    -------
    args : list
        Parser list of ``dest``.
    """
    return [act.dest for act in parser._actions if act.dest not in exclude]


def get_parser_action_by_dest(parser, dest):
    """
    Return parser action corresponding to ``dest``.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        Parser.

    dest : string
        Parser ``destination`` argument.

    Returns
    -------
    act : argparse._StoreAction
        Action.
    """
    for act in parser._actions:
        if act.dest == dest:
            return act
    return None


def sample_ra_dec(size=None, radecbox=(0.,360.,-90.,90.), rng=None, seed=None):
    """
    Sample uniform ra, dec coordinates in ``radecbox``.

    Taken from https://github.com/desihub/imaginglss/blob/master/scripts/imglss-mpi-make-random.py.

    Parameters
    ----------
    size : int, default=None
        Number of objects. If ``None``, only a single tuple ra, dec will be sampled.

    radecbox : list, tuple, default=(0.,360.,-90.,90.)
        ramin, ramax, decmin, decmax.

    rng : np.random.RandomState, default=None
        Random state; If ``None``, build RandomState from ``seed``.

    seed : int, default=None
        Random seed, only used if ``rng`` is None.

    Returns
    -------
    ra : float, ndarray
        Right ascension (degree).

    dec : float, ndarray
        Declination (degree).
    """
    if rng is None:
        rng = np.random.RandomState(seed=seed)

    ramin,ramax,decmin,decmax = radecbox

    u1,u2 = rng.uniform(size=(2,size) if size is not None else 2)
    #
    cmin = np.sin(np.deg2rad(decmin))
    cmax = np.sin(np.deg2rad(decmax))
    #
    ra = ramin + u1*(ramax-ramin)
    dec = 90.-np.rad2deg(np.arccos(cmin+u2*(cmax-cmin)))

    return ra, dec


def match_radec(ra1, dec1, ra2, dec2, radius_in_degree=None, return_distance=False, notself=False, nearest=True):
    """
    Match ra2,dec2 to ra1,dec1.

    All quantities in degree.
    Uses https://github.com/dstndstn/astrometry.net/blob/master/libkd/spherematch.py.

    Parameters
    ----------
    ra1 : array-like
        Right ascension 1 (degree).

    dec1 : array-like
        Declination 1 (degree).

    ra2 : array-like
        Right ascension 2 (degree).

    dec2 : array-like
        Declination 2 (degree).

    radius_in_degree : float,default=None
        If not None, maximum radius (degree) to match ra, dec pairs.

    return_distance : bool, default=False
        If ``True``, return distance.

    notself : bool, default=False
        If ``True``, avoids returning 'identity' matches, i.e. ra1,dec1 == ra2,dec2.

    nearest : bool, default=True
        If ``True``, returns only the nearest match in (ra2,dec2) for each point in (ra1,dec1).
        Else, returns all matches (index1 and index2 are not made of unique elements).

    Returns
    -------
    index1 : ndarray
        Indices of ra1,dec1 matching points.

    index2 : ndarray
        Indices of ra2,dec2 matching points.

    distance : ndarray
        Distance (degree).
    """
    provided_radius = radius_in_degree is not None
    if not provided_radius: radius_in_degree=360.
    index1,index2,distance = spherematch.match_radec(ra1,dec1,ra2,dec2,radius_in_degree,notself=notself,nearest=nearest)
    if provided_radius:
        mask = distance<radius_in_degree
        index1,index2,distance = index1[mask],index2[mask],distance[mask]

    if return_distance:
        return index1,index2,distance
    return index1, index2


def mask_collisions(ra, dec, radius_in_degree=5./3600.):
    """
    Return mask of collided objects.

    Parameters
    ----------
    ra : array-like
        Right ascension (degree).

    dec : array-like
        Declination (degree).

    radius_in_degree : float, default=5./3600.
        Collision radius (degree).

    Returns
    -------
    mask : bool ndarray
        Mask of collided objects.
    """
    skip = set()
    for ii,(ra_,dec_) in enumerate(zip(ra,dec)):
        if ii in skip: continue
        j = match_radec(ra_,dec_,ra,dec,radius_in_degree,
                            notself=False,nearest=False)[1]
        skip |= set(j[j!=ii]) # removes self-pair
    mask = np.zeros_like(ra,dtype=np.bool_)
    skip = np.array(list(skip))
    if skip.size:
        mask[skip] = True
    return mask


def get_radecbox_area(ramin, ramax, decmin, decmax):
    """
    Return area of ra, dec box.

    Parameters
    ----------
    ramin : float, array-like
        Minimum right ascension (degree).

    ramax : float, array-like
        Maximum right ascension (degree).

    decmin : float, array-like
        Minimum declination (degree).

    decmax : float, array-like
        Maximum declination (degree).

    Returns
    -------
    area : float, ndarray.
        Area (degree^2).
    """
    decfrac = np.diff(np.rad2deg(np.sin(np.deg2rad([decmin,decmax]))),axis=0)
    rafrac = np.diff([ramin,ramax],axis=0)
    area = decfrac*rafrac
    if np.isscalar(ramin):
        return area[0]
    return area


def get_shape_e(ba):
    """
    Return ellipticity ``e`` given minor-to-major axis ratio ``ba``.

    Parameters
    ----------
    ba : float, ndarray
        Minor-to-major axis ratio (b/a).

    Returns
    -------
    e : float, ndarray
        Ellipticity.

    References
    ----------
    https://www.legacysurvey.org/dr8/catalogs/
    Warning! Corresponds to g in: https://galsim-developers.github.io/GalSim/_build/html/shear.html#
    """
    return (1.-ba)/(1.+ba)


def get_shape_e1_e2(ba, phi):
    """
    Return ellipticities e1, e2 given minor-to-major axis ratio ``ba`` and angle ``phi``.

    Parameters
    ----------
    ba : float, ndarray
        Minor-to-major axis ratio (b/a).

    phi : float, ndarray
        Angle in radians.

    Returns
    -------
    e1 : float, ndarray
        Ellipticity component 1.

    e2 : float, ndarray
        Ellipticity component 2.

    References
    ----------
    https://www.legacysurvey.org/dr8/catalogs/
    """
    e = get_shape_e(ba)
    return e*np.cos(2*phi), e*np.sin(2*phi)


def get_shape_ba(e):
    """
    Return minor-to-major axis ratio ``ba`` given ellipticity ``e``.

    Parameters
    ----------
    e : float, ndarray
        Ellipticity.

    Returns
    -------
    ba : float, ndarray
        Minor-to-major axis ratio (b/a).

    References
    ----------
    https://www.legacysurvey.org/dr8/catalogs/
    """
    return (1.-np.abs(e))/(1.+np.abs(e))


def get_shape_ba_phi(e1, e2):
    """
    Return minor-to-major axis ratio ``ba`` and angle ``phi`` given ellipticities ``e1``, ``e2``.

    Parameters
    ----------
    e1 : float, ndarray
        Ellipticity component 1.

    e2 : float, ndarray
        Ellipticity component 2.

    Returns
    -------
    ba : float, ndarray
        Minor-to-major axis ratio (b/a).

    phi : float, ndarray
        Angle (radian).

    References
    ----------
    https://www.legacysurvey.org/dr8/catalogs/
    """
    ba = get_shape_ba((e1**2+e2**2)**0.5)
    phi = 0.5*np.arctan2(e2,e1) % (2.*np.pi)
    return ba, phi


def get_extinction(ra, dec, band=None, camera='DES'):
    """
    Return SFD extinction given ``ra``, ``dec``, ``band`` and ``camera``.

    If ``band`` not provided, return EBV.

    Parameters
    ----------
    ra : float, array-like
        Right ascension (degree).

    dec : float, array-like
        Declination (degree).

    band : string, default=None
        Photometric band. If not provided, returns EBV.

    camera : string, default=`DES`
        Camera.

    Returns
    -------
    extinction : float, ndarray
        Extinction.
    """
    from tractor.sfd import SFDMap
    sfd = SFDMap()
    if band is None:
        c = 1
    else:
        c = sfd.extinctions['%s %s' % (camera,band)]
    isscalar = np.isscalar(ra)
    ra,dec = np.asarray(ra),np.asarray(dec)
    toret = c*sfd.ebv(ra, dec)
    if isscalar:
        return toret[0]
    return toret


def mag2nano(mag):
    """Convert magnitudes to nanomaggies."""
    return 10. ** ((np.asarray(mag) - 22.5) / -2.5)


def nano2mag(nano):
    """Convert nanomaggies to magnitudes."""
    return 22.5 - 2.5 * np.log10(nano)


def match_id(id1,id2):
    """
    Match id2 to id1.

    Parameters
    ----------
    id1 : array-like
        IDs 1, should be unique.

    id2 : array-like
        IDs 2, should be unique.

    Returns
    -------
    index1 : ndarray
        Indices of matching ``id1``.

    index2 : ndarray
        Indices of matching ``id2``.

    Warning
    -------
    Makes sense only if ``id1`` and ``id2`` elements are unique.

    References
    ----------
    https://www.followthesheep.com/?p=1366
    """
    sort1 = np.argsort(id1)
    sort2 = np.argsort(id2)
    sortleft1 = id1[sort1].searchsorted(id2[sort2],side='left')
    sortright1 = id1[sort1].searchsorted(id2[sort2],side='right')
    sortleft2 = id2[sort2].searchsorted(id1[sort1],side='left')
    sortright2 = id2[sort2].searchsorted(id1[sort1],side='right')

    ind2 = np.flatnonzero(sortright1-sortleft1 > 0)
    ind1 = np.flatnonzero(sortright2-sortleft2 > 0)

    return sort1[ind1], sort2[ind2]
