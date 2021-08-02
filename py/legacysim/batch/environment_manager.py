"""
Script to set up environment for **legacysim** runs.

For details, run::

    python environment_manager.py --help

"""

import os
import sys
import logging
import argparse
import fitsio

from legacysim import find_file, RunCatalog, utils
from legacysim.catalog import Versions, Stages


logger = logging.getLogger('legacysim.environment_manager')


class EnvironmentManager(object):
    """
    Set up environment variables for **legacysim** runs. To be called as::

        with EnvironmentManager(...):
            # do legacysim-related stuff

    Attributes
    ----------
    header : fitsio.FITSHDR
        See below.

    environ : dict
        Environment variables.

    Note
    ----
    Only **legacypipe** and **legacysim** versions are saved for every stage in catalog headers.
    Other package versions are saved at the beginning of each run (stage 'tims'),
    and hence may not reflect the actual version used in any stage of the run.
    **legacypipe** catalog headers can be matched to a version of **legacypipe** Docker image (see :mod:`get_module_version`).
    However, for the same reason as above, this match may be ambiguous for any stage different than 'tims'.
    """

    _shorts_env = {'LARGEGALAXIES_CAT':'LARGEGALAXIES_CAT','TYCHO2_KD_DIR':'TYCHO2_KD',\
                    'GAIA_CAT_DIR':'GAIA_CAT','SKY_TEMPLATE_DIR':'SKY_TEMPLATE','GALEX_DIR':'galex',\
                    'UNWISE_COADDS_DIR':'unwise','UNWISE_COADDS_TIMERESOLVED_DIR':'unwise_tr','UNWISE_MODEL_SKY_DIR':'unwise_modelsky'}

    _check_env = {'LARGEGALAXIES_CAT':os.path.isfile,\
                'TYCHO2_KD_DIR':os.path.isdir,\
                'GAIA_CAT_DIR':os.path.isdir,\
                'SKY_TEMPLATE_DIR':os.path.isdir,\
                'GALEX_DIR':os.path.isdir,\
                'UNWISE_COADDS_DIR': lambda v: all(os.path.isdir(path) for path in v.split(':')),\
                'UNWISE_COADDS_TIMERESOLVED_DIR':os.path.isdir,\
                'UNWISE_MODEL_SKY_DIR':os.path.isdir}

    _shorts_stage = {'tims':'TIMS','refs':'REFS','outliers':'OUTL','halos':'HALO','srcs':'SRCS','fitblobs':'FITB',
                'coadds':'COAD','wise_forced':'WISE','writecat':'WCAT'}

    _docker_versions = []
    _docker_versions.append(('DR9.6.2',{'astrometry':'0.82','tractor':'dr9.4','legacypipe':'DR9.6.2'}))
    _docker_versions.append(('DR9.6.4',{'astrometry':'0.80-14-gf7363e4c','tractor':'dr9.3','legacypipe':'DR9.6.4'}))
    _docker_versions.append(('DR9.6.5',{'astrometry':'0.80-14-gf7363e4c','tractor':'dr9.3','legacypipe':'DR9.6.5'}))
    _docker_versions.append(('DR9.6.5b',{'astrometry':'0.80-14-gf7363e4c','tractor':'dr9.3','legacypipe':'DR9.6.5-4-gbb698724'}))
    _docker_versions.append(('DR9.6.6',{'astrometry':'0.83','tractor':'dr9.4','legacypipe':'DR9.6.6'}))
    _docker_versions.append(('DR9.6.7',{'astrometry':'0.83','tractor':'dr9.4','legacypipe':'DR9.6.7'}))
    _docker_versions.append(('DR9.6.7',{'astrometry':'0.83-1-g4a4c1bfe','tractor':'dr9.4','legacypipe':'DR9.6.7'})) # not satisfactory, but too much of a pain to rebuild with NERSC compilers
    _docker_versions.append(('DR9.6.7b',{'astrometry':'0.84','tractor':'dr9.4','legacypipe':'DR9.6.7'}))
    _docker_versions.append(('DR9.6.8',{'astrometry':'0.84-15-g48bdcb08','tractor':'dr9.4','legacypipe':'DR9.6.8'}))
    _docker_versions.append(('DR9.6.9',{'astrometry':'0.84-15-g48bdcb08','tractor':'dr9.5','legacypipe':'DR9.6.9'}))

    def __init__(self, header=None, fn=None, base_dir=None, brickname=None, source='legacypipe', filetype=None, kwargs_simid=None, skip=False):
        """
        Initialize :class:`EnvironmentManager` by reading the primary header of an output catalog.

        Parameters
        ----------
        header : FITSHDR, default=None
            FITS header to read environment from. If not ``None``,
            supersedes ``fn``, ``base_dir``, ``brickname``, ``source``, ``filetype``, ``kwargs_simid``.
            ``header`` is copied into :attr:`header`.

        fn : string, default=None
            Name of **Tractor** file to read header from.
            If not ``None``, supersedes ``base_dir``, ``brickname``, ``source``, ``filetype``, ``kwargs_simid``.

        base_dir : string, default=None
            **legacysim** (if ``source == 'legacysim'``) or legacypipe (if ``source == 'legacypipe'``) root file directory.

        brickname : string, default=None
            Brick name.

        source : string, default='legacysim'
            If 'legacysim', search for an **legacysim** file name, else a **legacypipe** file name.

        filetype : string, default=None
            File type to read primary header from.
            If ``None``, defaults to 'injected' if ``source == 'legacysim'``, else 'tractor'.

        kwargs_simid : dict, default=None
            :class:`~legacysim.survey.get_sim_id` dictionary with keys :meth:`~legacysim.survey.get_sim_id.keys`.

        skip : bool, default=False
            If ``True``, do not set environment.
        """
        self.environ = {}
        if skip:
            return
        if header is not None:
            self.header = header.__class__()
            # copy for security
            for record in header.records():
                self.header.add_record(record.copy())
        else:
            self.fn = fn
            if self.fn is None:
                if filetype is None:
                    if source == 'legacysim':
                        filetype = 'injected'
                    else:
                        filetype = 'tractor'
                kwargs_simid = kwargs_simid or {}
                self.fn = find_file(base_dir=base_dir,filetype=filetype,brickname=brickname,source=source,**kwargs_simid)
            self.header = fitsio.read_header(self.fn)
        # hack, since DR9.6.2 had no VER_TIMS entry
        if 'VER_TIMS' not in self.header: self.header['VER_TIMS'] = self.header['LEGPIPEV']
        #print('OSENVIRON',os.environ)
        self.set_environ()

    def __enter__(self):
        """Save current environment variables and enter new environment."""
        self._back_environ = dict(os.environ)
        self.check_environ()
        os.environ.update(self.environ)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Exit current environment and reset previous environment variables."""
        os.environ.clear()
        os.environ.update(self._back_environ)

    def set_environ(self):
        """Set environment variables :attr:`environ`."""
        self.environ = {}
        msg = 'Setting environment variable %s = %s'
        for name,keyw in self._shorts_env.items():
            value = None
            for key in self.header:
                if key.startswith('DEPNAM') and self.header[key] == keyw:
                    value = self.header[key.replace('DEPNAM','DEPVER')]
                    break
            if value is not None:
                logger.info(msg,name,value)
                self.environ[name] = value

    def check_environ(self):
        """
        Check whether variables in :attr:`environ` are valid (typically if directory or file exists on disk); else fall back to :attr:`os.environ`.

        Raises
        ------
        ValueError : If a variable in :attr:`environ` is not valid and there is no fallback value in :attr:`os.environ`.
        """
        for name,value in self.environ.items():
            if name not in self._check_env: continue
            if not self._check_env[name](value):
                if name not in os.environ:
                    raise ValueError('Header value %s = %s is not valid and no corresponding environment variable is set.' % (name,value))
                env_value = os.environ[name]
                logger.warning('Header value %s = %s is not valid.',name,value)
                logger.warning('Falling back to the environment value %s = %s.',name,env_value)
                self.environ[name] = env_value

    def get_module_version(self, module, stage='writecat'):
        """
        Return module version for stage.

        **legacypipe** and **legacysim** runs are performed within a Docker container.
        To return (one of) the Docker image version that matches the module versions in the catalog header,
        pass ``module == 'docker'``.

        Parameters
        ----------
        module : string
            Module name.
            If 'docker', return a Docker image version by matching module versions to internal :attr:`_docker_versions`.
            If ``stage == 'tims'`` or **legacypipe** versions are the same for every stage up to ``stage``, match all modules of :attr:`_docker_versions`;
            else only **legacypipe** version (at the given stage) is matched to :attr:`_docker_versions`,
            and the last Docker image version of the obtained matches is returned.

        stage : string, default='writecat'
            Stage name.

        Returns
        -------
        version : string
            Module version.
        """
        if stage not in self._shorts_stage:
            raise ValueError('Do not know stage %s. Should be on of %s' % (stage,Stages.all()))
        if module == 'docker':
            check_all = stage == 'tims'
            if not check_all:
                versions = set()
                for s in Stages.all():
                    versions.add(self.get_module_version('legacypipe',s))
                    if s == stage:
                        break
                check_all |= len(versions) == 1
            for docker,versions in self._docker_versions[::-1]:
                modules = versions.keys() if check_all else ['legacypipe']
                eq = True
                for mod in modules:
                    if self.get_module_version(mod,stage=stage) != versions[mod]:
                        eq = False
                        break
                if eq:
                    return docker
            raise ValueError('Could not find matching %s version for stage %s and modules %s in header: %s' % (module,stage,list(modules),self.header))
        key = None
        if module == 'legacypipe':
            key = 'VER_%s' % self._shorts_stage[stage]
        elif module == 'legacysim':
            key = 'LSV_%s' % self._shorts_stage[stage]
        else:
            for k in self.header:
                if k.startswith('DEPNAM') and self.header[k] == module:
                    key = k.replace('DEPNAM','DEPVER')
                    break
        if key is None or key not in self.header:
            raise ValueError('Could not find version information on module %s for stage %s in header: %s' % (module,stage,self.header))
        return self.header[key]

    def get_stages_versions(self, modules):
        """
        Return a :class:`Stages` instance with changes in module versions (at least including 'writecat').

        Parameters
        ----------
        modules : list
            List of module names to get versions for.

        Returns
        -------
        stages : Stages
            Stages with mapping (stage name, module versions).
        """
        stage_names = Stages.all()[::-1]

        def get_stage_versions(stage):
            return Versions(**{module:self.get_module_version(module,stage) for module in modules})

        try:
            get_stage_versions('wise_forced')
        except ValueError:
            stage_names.remove('wise_forced') # when wise not run, keyword not added in header

        last_stage = stage_names[0]
        stages = Stages([(last_stage,get_stage_versions(last_stage))])
        for stage in stage_names[1:]:
            versions = get_stage_versions(stage)
            if versions != stages[last_stage]:
                stages[stage] = versions
                last_stage = stage
        return stages


def get_pythonpath(module_dir='/src/',versions=(),full=False,as_string=False):
    """
    Return PYTHONPATH.

    The path to 'module' is set to ``module_dir``/module_version(/py for **legacypipe** and **legacysim** modules).

    Parameters
    ----------
    module_dir : string, default='/src/'
        Directory containing modules.

    versions : Versions, dict, list of tuples, default=()
        (module, version) mapping.

    full : bool, default=False
        By default, only PYTHONPATH to modules in ``versions`` is returned.
        If ``full == True``, append other paths already in current PYTHONPATH.

    as_string : bool, default=False
        By default, returned value is a list of paths.
        If ``as_string == True``, return a string with paths separated by a colon ':'.

    Returns
    -------
    pythonpath : string, list of strings
        PYTHONPATH.
    """
    suffixes_module = {'legacysim':'py','legacypipe':'py','unwise_psf':'py'}
    pythonpath = []
    versions = dict(versions)
    for module in versions:
        path = os.path.join(module_dir,'%s_%s' % (module,versions[module]),suffixes_module.get(module,''))
        if not os.path.isdir(path):
            raise ValueError('No directory found in %s' % path)
        pythonpath.insert(0,path)
    if full:
        for path in os.environ['PYTHONPATH'].split(':'):
            if path not in pythonpath: pythonpath.append(path)
    if as_string:
        pythonpath = ':'.join(pythonpath)
    return pythonpath


def main(args=None):
    """Print all module paths and environment variables used for the run(s)."""
    #from legacysim import setup_logging
    #setup_logging()
    logging.disable(sys.maxsize)
    parser = argparse.ArgumentParser(description=main.__doc__,formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--module-dir', type=str, default='/src/', help='Directory containing modules')
    parser.add_argument('--modules', type=str, nargs='*', default=['docker'], help='Modules to add in the PYTHONPATH. \
                        Pass "docker" to add in the PYTHONPATH a directory containing packages of the corresponding legacypipe Docker image.')
    parser.add_argument('--stage', type=str, choices=Stages.all(), default='fitblobs',
                        help='Version for this stage')
    parser.add_argument('--full-pythonpath', action='store_true', default=False,
                        help='Print full PYTHONPATH')
    parser.add_argument('--check-environ', action='store_true', default=False,
                        help='Check environment variables are valid (typically if directory or file exists on disk)')
    RunCatalog.get_output_parser(parser=parser,add_source=True)
    utils.get_parser_action_by_dest(parser,'source').default = 'legacypipe'
    opt = parser.parse_args(args=utils.get_parser_args(args))
    runcat = RunCatalog.from_output_cmdline(opt)

    environ,versions = [],[]
    for run in runcat:
        environment = EnvironmentManager(base_dir=opt.output_dir,brickname=run.brickname,source=opt.source,kwargs_simid=run.kwargs_simid)
        if opt.check_environ:
            environment.check_environ()
        for key,val in environment.environ.items():
            tmp = '%s=%s' % (key,val)
            if tmp not in environ: environ.append(tmp)
        for module in opt.modules:
            tmp = module,environment.get_module_version(module=module,stage=opt.stage)
            if tmp not in versions: versions.append(tmp)

    pythonpath = get_pythonpath(module_dir=opt.module_dir,versions=versions,full=opt.full_pythonpath,as_string=True)
    print('PYTHONPATH=%s' % pythonpath)
    for v in environ:
        print(v)
    logging.disable(logging.NOTSET)


if __name__ == '__main__':

    main()
