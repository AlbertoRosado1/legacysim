"""
Script to set up environment for **Obiwan** runs.

For details, run::

    python environment_manager.py --help

"""

import os
import sys
import re
import logging
import argparse
import fitsio

from obiwan import find_file,RunCatalog,utils
from obiwan.catalog import Versions,Stages


logger = logging.getLogger('obiwan.environment_manager')


class EnvironmentManager(object):
    """
    Set up environment variables for **Obiwan** runs. To be called as::

        with EnvironmentManager(...):
            # do Obiwan-related stuff

    Attributes
    ----------
    header : fitsio.FITSHDR
        See below.

    environ : dict
        Environment variables.
    """

    shorts_env = {'LARGEGALAXIES_CAT':'LARGEGALAXIES_CAT','TYCHO2_KD_DIR':'TYCHO2_KD',\
                    'GAIA_CAT_DIR':'GAIA_CAT','SKY_TEMPLATE_DIR':'SKY_TEMPLATE','GALEX_DIR':'galex'}

    keys_env = {'UNWISE_COADDS_DIR':'UNWISD(?P<i>.*?)$','UNWISE_COADDS_TIMERESOLVED_DIR':'UNWISTD',\
                'UNWISE_MODEL_SKY_DIR':'UNWISSKY'}

    shorts_stage = {'tims':'TIMS','refs':'REFS','outliers':'OUTL','halos':'HALO','srcs':'SRCS','fitblobs':'FITB',
                'coadds':'COAD','wise_forced':'WISE','writecat':'WCAT'}

    def __init__(self, header=None, fn=None, base_dir=None, brickname=None, source='legacypipe', filetype=None, kwargs_file=None, skip=False):
        """
        Initialize :class:`EnvironmentManager` by reading the primary header of an output catalog.

        Parameters
        ----------
        header : FITSHDR, default=None
            FITS header to read environment from. If not ``None``,
            supersedes ``fn``, ``base_dir``, ``brickname``, ``source``, ``filetype``, ``kwargs_file``.
            ``header`` is copied into :attr:`header`.

        fn : string, default=None
            Name of **Tractor** file to read header from.
            If not ``None``, supersedes ``base_dir``, ``brickname``, ``source``, ``filetype``, ``kwargs_file``.

        base_dir : string, default=None
            **Obiwan** (if ``source == 'obiwan'``) or legacypipe (if ``source == 'legacypipe'``) root file directory.

        brickname : string, default=None
            Brick name.

        source : string, default='obiwan'
            If 'obiwan', search for an **Obiwan** file name, else a **legacypipe** file name.

        filetype : string, default=None
            File type to read primary header from.
            If ``None``, defaults to 'randoms' if ``source == 'obiwan'``, else 'tractor'.

        kwargs_file : dict, default=None
            Other arguments to file paths (e.g. :func:`obiwan.kenobi.get_randoms_id.keys`).

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
                    if source == 'obiwan':
                        filetype = 'randoms'
                    else:
                        filetype = 'tractor'
                kwargs_file = kwargs_file or {}
                self.fn = find_file(base_dir=base_dir,filetype=filetype,brickname=brickname,source=source,**kwargs_file)
            self.header = fitsio.read_header(self.fn)
        # hack, since DR9.6.2 had no VER_TIMS entry
        if 'VER_TIMS' not in self.header: self.header['VER_TIMS'] = self.header['LEGPIPEV']
        self.set_environ()

    def __enter__(self):
        """Save current environment variables and enter new environment."""
        self._back_environ = os.environ.copy()
        os.environ.update(self.environ)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Exit current environment and reset previous environment variables."""
        os.environ = self._back_environ.copy()

    def set_environ(self):
        """Set environment variables :attr:`environ`."""
        self.environ = {}
        msg = 'Setting environment variable %s = %s'
        for name,keyw in self.shorts_env.items():
            value = None
            for key in self.header:
                if key.startswith('DEPNAM') and self.header[key] == keyw:
                    value = self.header[key.replace('DEPNAM','DEPVER')]
                    break
            if value is not None:
                logger.info(msg,name,value)
                self.environ[name] = value
        for name,keyw in self.keys_env.items():
            value = None
            for key in self.header:
                if key == keyw:
                    value = self.header[key]
                    break
                if re.fullmatch(keyw,key):
                    if value is None:
                        value = self.header[key]
                    else:
                        value = '%s:%s' % (value,self.header[key])
            if value is not None:
                logger.info(msg,name,value)
                self.environ[name] = value

    def get_module_version(self, module, stage='writecat'):
        """
        Return module version for stage.

        Parameters
        ----------
        module : string
            Module name.

        stage : string, default='writecat'
            Stage name.

        Returns
        -------
        version : string
            Module version.
        """
        if stage not in self.shorts_stage:
            raise ValueError('Do not know stage %s. Should be on of %s' % (stage,Stages.all()))
        key = None
        if module == 'legacypipe':
            key = 'VER_%s' % self.shorts_stage[stage]
        elif module == 'obiwan':
            key = 'OBV_%s' % self.shorts_stage[stage]
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

    The path to 'module' is set to ``module_dir``/module_version(/py for **legacypipe** and **Obiwan** modules).

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
    suffixes_module = {'legacypipe':'py','obiwan':'py'}
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
    #from obiwan import setup_logging
    #setup_logging()
    logging.disable(sys.maxsize)
    parser = argparse.ArgumentParser(description='EnvironmentManager',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--module-dir', type=str, default='.', help='Directory containing modules')
    parser.add_argument('--modules', type=str, nargs='*', default=['legacypipe'], help='Modules to search version for')
    parser.add_argument('--stage', type=str, choices=Stages.all(), default='fitblobs',
                        help='Version for this stage')
    parser.add_argument('--full-pythonpath', action='store_true', default=False,
                        help='Print full PYTHONPATH')
    RunCatalog.get_output_parser(parser=parser,add_source=True)
    utils.get_parser_action_by_dest(parser,'source').default = 'legacypipe'
    opt = parser.parse_args(args=utils.get_parser_args(args))
    runcat = RunCatalog.from_output_cmdline(opt)

    environ,versions = [],[]
    for run in runcat:
        environment = EnvironmentManager(base_dir=opt.output_dir,brickname=run.brickname,source=opt.source,kwargs_file=run.kwargs_file)
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
