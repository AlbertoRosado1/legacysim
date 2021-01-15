"""Classes to extend :mod:`legacypipe.survey`."""

import os
import re
import logging

from legacypipe.survey import LegacySurveyData
from legacypipe.runs import DecamSurvey, NinetyPrimeMosaic
from legacypipe.runcosmos import CosmosSurvey

from .image import DecamSimImage, DecamSimImagePlusNoise, MosaicSimImage, BokSimImage, PtfSimImage, MegaPrimeSimImage

logger = logging.getLogger('legacysim.survey')


def get_git_version(dirnm=None):
    """
    Run 'git describe' in the current directory (or given dir) and return the result as a string.

    Parameters
    ----------
    dirnm : string, default=None
        If not ``None``, 'cd' to the given directory before running 'git describe'.

    Returns
    -------
    version : string
        Git version.

    Notes
    -----
    Taken from https://github.com/legacysurvey/legacypipe/blob/master/py/legacypipe/survey.py
    """
    from legacypipe.survey import get_git_version as get_legacypipe_git_version
    if dirnm is None:
        import legacysim
        dirnm = os.path.dirname(legacysim.__file__)
    return get_legacypipe_git_version(dirnm=dirnm)


def get_version():
    """Return :func:`get_git_version` if not empty, else :attr:`legacysim.__version__`."""
    toret = get_git_version()
    if not toret:
        from ._version import __version__
        toret = __version__
    return toret


class get_sim_id(object):
    """Handle identifier related to simulation: file id, row start, skip id."""

    _keys = ['fileid','rowstart','skipid']
    _default = [0]*len(_keys)
    _template = 'file%s_rs%s_skip%s'
    _kwargs_match_template = {key:'(?P<%s>.*?)' % key for key in _keys}

    @classmethod
    def keys(cls):
        """Return keys."""
        return cls._keys

    @classmethod
    def default(cls):
        """Return default values."""
        return cls._default

    @classmethod
    def template(cls):
        """Return string template."""
        return cls._template

    @classmethod
    def kwargs_match_template(cls):
        """Return kwargs to reconstruct match template."""
        return cls._kwargs_match_template

    @classmethod
    def match_template(cls):
        """Return match template."""
        return cls._template % tuple(cls._kwargs_match_template[key] for key in cls.keys())

    @classmethod
    def as_dict(cls, **kwargs):
        """Return sim id kwargs corresponding to kwargs."""
        return {key_: kwargs.get(key_,def_) for key_,def_ in zip(cls.keys(),cls.default())}

    @classmethod
    def as_list(cls, **kwargs):
        """Return list corresponding to sim id kwargs."""
        toret = cls.as_dict(**kwargs)
        return [toret[key_] for key_ in cls.keys()]

    def __new__(cls, **kwargs):
        """Return string corresponding to sim id kwargs."""
        return cls._template % tuple(cls.as_list(**kwargs))

    @classmethod
    def match(cls,string):
        """Match sim id in ``string`` and return sim id kwargs."""
        match = re.match(cls.match_template() + '$',string)
        return {key: int(match.group(key)) for key in cls.keys()}


def find_file(base_dir=None, filetype=None, brickname=None, source='legacysim', **kwargs):
    """
    Return file name.

    Shortcut to :meth:`LegacySurveySim.find_file`.

    base_dir : string, default=None
        **legacysim** (if ``source == 'legacysim'``) or legacypipe (if ``source == 'legacypipe'``) root file directory.

    filetype : string, default=None
        Type of file to find.

    brickname : string, default=None
        Brick name.

    source : string, default='legacysim'
        If 'legacysim', return an **legacysim** output file name, else a **legacypipe** file name.

    kwargs : dict
        Other arguments to file paths (e.g. :meth:`get_sim_id.keys`).
    """
    if source == 'legacysim':
        survey = LegacySurveySim(survey_dir=base_dir,output_dir=base_dir,kwargs_simid=get_sim_id.as_dict(**kwargs))
    else:
        survey = LegacySurveyData(survey_dir=base_dir,output_dir=base_dir)
    kwargs = {key:val for key,val in kwargs.items() if key not in get_sim_id.keys()}
    return survey.find_file(filetype,brick=brickname,output=False,**kwargs)


def find_legacypipe_file(survey_dir, filetype, brickname=None, **kwargs):
    """
    Return **legacypipe** file name.

    survey_dir : string
        Survey directory.

    filetype : string
        Type of file to find.

    brickname : string
        Brick name.

    kwargs : dict
        Other arguments to file paths (e.g. :meth:`get_sim_id.keys`).
    """
    return find_file(base_dir=survey_dir,filetype=filetype,brickname=brickname,source='legacypipe',**kwargs)


def find_legacysim_file(output_dir, filetype, brickname=None, **kwargs):
    """
    Return **legacysim** output file name.

    output_dir : string
        **legacysim** output directory.

    filetype : string
        Type of file to find.

    brickname : string
        Brick name.

    kwargs : dict
        Other arguments to file paths (e.g. :meth:`get_sim_id.keys`).
    """
    return find_file(base_dir=output_dir,filetype=filetype,brickname=brickname,source='legacysim',**kwargs)


class BaseSimSurvey(object):
    """
    Dumb class with **legacysim** attributes for future multiple inheritance.

    Attributes
    ----------
    injected : SimCatalog
        See below.

    sim_stamp : string
        See below.

    add_sim_noise : string
        See below.

    image_eq_model : bool
        See below.

    kwargs_simid : dict
        See below.

    rng : numpy.random.RandomState
        Random state, from :attr:`seed``.

    image_typemap : dict
        Mapping (camera,class) used by :class:`legacypipe.survey.LegacySurveyData`.

    survey_dir : string
        Directory containing input imaging data.

    output_dir : string
        Directory containing output catalogs.
    """

    def __init__(self, *args, injected=None, sim_stamp='tractor', add_sim_noise=False,
                 image_eq_model=False, kwargs_simid=None, **kwargs):
        """
        kwargs are to be passed on to :class:`legacypipe.survey.LegacySurveyData`-inherited classes, other arguments are specific to :class:`BaseSimSurvey`.
        Only ``survey_dir`` must be specified to obtain bricks through :meth:`get_brick_by_name`.

        Parameters
        ----------
        injected : SimCatalog, default=None
            Catalog of sources to inject in a given brick (not CCD).

        sim_stamp : string, default='tractor'
            Method to simulate sources, either 'tractor' (:class:`TractorSimStamp`) or 'galsim' (:class:`GalSimStamp`).

        add_sim_noise : string, default=False
            Add noise related to the simulated source to the image. Choices: ['gaussian','poisson'].

        image_eq_model : bool, default=False
            Wherever add a simulated source, replace both image and inverse variance of the image
            with that of the simulated source only.

        kwargs_simid : dict, default=None
            :class:`get_sim_id` dictionary with keys :meth:`get_sim_id.keys`.

        kwargs : dict
            Arguments for :class:`legacypipe.survey.LegacySurveyData`.
        """
        super(BaseSimSurvey, self).__init__(*args,**kwargs)
        self.image_typemap = {
            'decam': DecamSimImage,
            'decam+noise': DecamSimImagePlusNoise,
            'mosaic': MosaicSimImage,
            'mosaic3': MosaicSimImage,
            '90prime': BokSimImage,
            'ptf': PtfSimImage,
            'megaprime': MegaPrimeSimImage,
            }
        kwargs_simid = kwargs_simid or {}
        for key in ['injected','sim_stamp','add_sim_noise','image_eq_model','kwargs_simid']:
            setattr(self,key,locals()[key])

    def find_file(self, filetype, brick=None, output=False, stage=None, **kwargs):
        """
        Return the file name of a Legacy Survey file.

        Parameters
        ----------
        filetype : string
            Type of file to find, including:
            - 'injected': injected sources
            - 'pickle': pickle files
            - 'checkpoint': checkpoint files
            - 'log' : log files
            - 'ps' : ps (resources time series) catalogs
            - 'tractor': **Tractor** catalogs
            - 'depth': PSF depth maps
            - 'galdepth': canonical galaxy depth maps
            - 'nexp': number-of-exposure maps.

        brick : string, defaut=None
            Brick name.

        output : bool, default=False
            Whether we are about to write this file; will use :attr:`output_dir` as
            the base directory rather than :attr:`survey_dir`.

        stage : string, default=None
            Stage, only used if ``filetype == 'pickle'``.

        kwargs : dict
            Arguments for :meth:`legacypipe.survey.LegacySurveyData.find_file`.

        Returns
        -------
        fn : string
            Path to the specified file (whether or not it exists).
        """
        if brick is None:
            brickname = '%(brick)s'
            brickpre = '%(brick).3s'
        else:
            brickname = brick
            brickpre = brick[:3]

        if stage is None:
            stage = '%(stage)s'

        simid = get_sim_id(**self.kwargs_simid)

        if filetype == 'injected':
            base_dir = os.path.join(self.output_dir,simid,'sim',brickpre)
            return os.path.join(base_dir,'injected-%s.fits' % brickname)
        if filetype == 'pickle':
            base_dir = os.path.join(self.output_dir,simid,'pickles',brickpre)
            return os.path.join(base_dir,'runbrick-%s-%s.pickle' % (brickname,stage))
        if filetype == 'checkpoint':
            base_dir = os.path.join(self.output_dir,simid,'checkpoints',brickpre)
            return os.path.join(base_dir,'checkpoint-%s.pickle' % brickname)
        if filetype == 'log':
            base_dir = os.path.join(self.output_dir,simid,'logs',brickpre)
            return os.path.join(base_dir,'log-%s.log' % brickname)
        if filetype == 'ps':
            base_dir = os.path.join(self.output_dir,simid,'metrics',brickpre)
            return os.path.join(base_dir,'ps-%s.fits' % brickname)

        fn = super(BaseSimSurvey,self).find_file(filetype,brick=brick,output=output,**kwargs)

        def wrap(fn):
            relname = os.path.relpath(fn,self.output_dir if output else self.survey_dir)
            legpipe_dir = os.path.normpath(relname).split(os.path.sep)[0]
            if legpipe_dir in ['metrics','coadd','tractor-i','tractor']:
                return os.path.join(self.output_dir,simid,relname)
            return fn

        if isinstance(fn,list):
            fn = list(map(wrap,fn))
        elif fn is not None:
            fn = wrap(fn)

        return fn


class LegacySurveySim(BaseSimSurvey,LegacySurveyData):
    """Extend :class:`BaseSimSurvey` with :class:`legacypipe.survey.LegacySurveyData`."""


class CosmosSim(BaseSimSurvey,CosmosSurvey):
    """
    Extend :class:`BaseSimSurvey` with a filter for cosmos CCDs.

    Call with BaseSimSurvey arguments plus additional CosmosSurvey argument ``subset``.
    """


class DecamSim(BaseSimSurvey,DecamSurvey):
    """Extend :class:`BaseSimSurvey` with a filter for DECam CCDs."""


class NinetyPrimeMosaicSim(BaseSimSurvey,NinetyPrimeMosaic):
    """Extend :class:`BaseSimSurvey` with a filter for mosaic or 90prime CCDs."""


runs = {
    'decam': DecamSim,
    '90prime-mosaic': NinetyPrimeMosaicSim,
    'south': DecamSim,
    'north': NinetyPrimeMosaicSim,
    'cosmos': CosmosSim,
    None: LegacySurveySim,
}


def get_survey(name, **kwargs):
    """
    Return an instance of the :class:`BaseSimSurvey`-inherited class given by name.

    See :attr:`legacysim.survey.runs` dictionary.
    """
    survey_class = runs[name]
    if name != 'cosmos':
        kwargs.pop('subset',None)
    survey = survey_class(**kwargs)
    return survey
