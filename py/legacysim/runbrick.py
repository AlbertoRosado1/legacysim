"""**legacysim** main executable, extend :mod:`legacypipe.runbrick`."""

import os
import sys
import argparse
import logging

import numpy as np
import legacypipe
from legacypipe import runbrick
from legacypipe.utils import RunbrickError, NothingToDoError

from legacysim import SimCatalog, utils, setup_logging
from legacysim.utils import MonkeyPatching
from legacysim.batch import EnvironmentManager


logger = logging.getLogger('legacysim.runbrick')


def wrapper_get_version_header(legacypipe_get_version_header):
    """Wrap :func:`legacypipe.survey.get_version_header` to add **legacysim** version."""
    def get_version_header(*args, **kwargs):
        import fitsio
        from legacysim.survey import get_version
        hdr = fitsio.FITSHDR()
        s = 'legacysim running legacypipe'
        hdr.add_record(dict(name='COMMENT',value=s,comment=s))
        hdr.add_record(dict(name='LEGSIMV',value=get_version(),comment='legacysim git version'))
        for record in legacypipe_get_version_header(*args,**kwargs).records():
            hdr.add_record(record)
        return hdr
    return get_version_header


def wrapper_get_dependency_versions(legacypipe_get_dependency_versions):
    """Wrap :func:`legacypipe.survey.get_dependency_versions` to add **legacysim** dependency versions (galsim)."""
    def get_dependency_versions(*args, **kwargs):
        headers = legacypipe_get_dependency_versions(*args,**kwargs)
        import galsim
        name,value = 'galsim',galsim.__version__
        i = int(headers[-1][0].replace('DEPVER','')) + 1
        headers.append(('DEPNAM%02i' % i, name, ''))
        headers.append(('DEPVER%02i' % i, value, ''))
        return headers
    return get_dependency_versions


def wrapper_add_stage_version(legacypipe_add_stage_version):
    """Wrap :func:`legacypipe.runbrick._add_stage_version` to add **legacysim** stage version."""
    def _add_stage_version(version_header, short, stagename):
        from legacysim.survey import get_version
        version_header.add_record(dict(name='LSV_%s'%short, value=get_version(),
                                       help='legacysim version for stage_%s'%stagename))
        legacypipe_add_stage_version(version_header, short, stagename)
    return _add_stage_version


def get_parser():
    """
    Append **legacysim** arguments to those of :func:`legacypipe.runbrick.get_parser`.

    Returns
    -------
    parser : argarse.ArgumentParser
        Parser.

    args_runbrick : list
        List of **legacypipe**-specific arguments.
    """
    de = ('Main "legacysim" script for the Legacy Survey (DECaLS, MzLS, Bok) data reductions.')
    ep = """
    e.g., to run a small field containing a cluster:
python -u legacysim/runbrick.py --plots --brick 2440p070 --zoom 1900 2400 450 950 -P pickles/runbrick-cluster-%%s.pickle"""
    parser = argparse.ArgumentParser(description=de,epilog=ep,add_help=False,parents=[runbrick.get_parser()],
                                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    pickle_pat = utils.get_parser_action_by_dest(parser,'pickle_pat')
    pickle_pat.help = 'Pickle file name pattern, if not provided, used the default file name (in "outdir/pickle")'
    pickle_pat.default = None

    checkpoint_filename = utils.get_parser_action_by_dest(parser,'checkpoint_filename')
    checkpoint_filename.help = 'Write to checkpoint to file name. If file name is not provided, used the default file name (in "outdir/checkpoint")'
    checkpoint_filename.default = None
    checkpoint_filename.const = True
    checkpoint_filename.nargs = '?'

    args_runbrick = utils.list_parser_dest(parser,exclude=['verbose','help'])
    # legacysim arguments
    group = parser.add_argument_group(title='legacysim',description='legacysim-specific arguments')
    group.add_argument('--subset', type=int, default=0,
                        help='COSMOS subset number [0 to 4, 10 to 12], only used if --run cosmos')
    group.add_argument('--injected-fn', default=None, help='File name of injected sources; if not provided, run equivalent to legacypipe.runbrick')
    group.add_argument('--fileid', type=int, default=0, help='ID of injected sources')
    group.add_argument('--rowstart', type=int, default=0,
                        help='Zero indexed, row of injected-fn, after it is cut to brick, to start from')
    group.add_argument('--nobj', type=int, default=-1,
                        help='Number of sources to inject in the given brick; if -1, all sources in injected-fn are added')
    group.add_argument('--skipid', type=int, default=0, help='Inject collided sources from injected-fn of previous skipid-1 run. \
                       In this case, no cut based on --nobj and --rowstart is applied')
    group.add_argument('--col-radius', type=float, default=5., help='Collision radius in arcseconds, used to define collided simulated objects. \
                        Ignore if negative')
    group.add_argument('--sim-stamp', type=str, choices=['tractor','galsim'], default='tractor', help='Method to simulate objects')
    group.add_argument('--add-sim-noise', type=str, choices=['gaussian','poisson'], default=False, help='Add noise from the simulated source to the image.')
    group.add_argument('--image-eq-model', action='store_true', default=False, help='Set image ivar by model only (ignore real image ivar)?')
    group.add_argument('--sim-blobs', action='store_true', default=False,
                        help='Process only the blobs that contain injected sources')
    group.add_argument('--seed', type=int, default=None, help='Random seed to add noise to sources of injected-fn. \
                        Used to fill or replace `seed` column if provided.')
    parser.add_argument('--env-header', type=str, default=None, help='Catalog file name to read header from to setup environment variables. \
                        If not provided, environment is not updated.')
    parser.add_argument('--write-log', nargs='?', type=str, default=None, const=True, help='Write log to given file name instead of stdout. \
                        If file name is not provided, use the default file name (in "outdir/logs")')
    parser.add_argument('--ps', nargs='?', type=str, default=False, const=True,
                        help='Run "ps" and write results to file name. \
                        If file name is not provided, use the default file name (in "outdir/metrics")')
    parser.add_argument('--ps-t0', type=int, default=0, help='Unix-time start for "--ps"')
    return parser, args_runbrick


def get_runbrick_kwargs(args_runbrick, **opt):
    """
    Convert :mod:`legacysim.runbrick` command line options into ``survey`` and ``**kwargs`` for :func:`run_brick`.

    Wraps :func:`legacypipe.runbrick.get_runbrick_kwargs`.

    Parameters
    ----------
    args_runbrick : list
        List of **legacypipe**-specific arguments.

    opt : dict
        Dictionary of the command line options for :mod:`legacysim.runbrick`.

    Returns
    -------
    survey : LegacySurveySim instance
        Survey, without ``injected``.

    kwargs : dict
        Arguments for :func:`legacypipe.runbrick.run_brick` following::

            run_brick(brickname, survey, **kwargs)

    """
    from legacysim.survey import get_sim_id
    opt['kwargs_simid'] = get_sim_id.as_dict(**opt)
    kwargs_survey = {key:opt[key] for key in \
                          ['sim_stamp','add_sim_noise','image_eq_model','kwargs_simid',
                           'survey_dir','output_dir','cache_dir','subset']}
    from legacysim.survey import get_survey
    survey = get_survey(opt.get('run',None),**kwargs_survey)
    logger.info(survey)
    if opt['pickle_pat'] is None:
        opt['pickle_pat'] = survey.find_file('pickle',brick=None,stage='%%(stage)s')
    else:
        opt['pickle_pat'] = opt['pickle_pat'].replace('%(simid)s',get_sim_id(**opt['kwargs_simid']))

    if opt['checkpoint_filename']:
        if not isinstance(opt['checkpoint_filename'],str):
            opt['checkpoint_filename'] = survey.find_file('checkpoint',brick=opt['brick'])

    if opt['radec'] is not None:
        opt['brick'] = None

    survey,kwargs = runbrick.get_runbrick_kwargs(survey,**{key:opt[key] for key in args_runbrick})

    return survey, kwargs


def run_brick(opt, survey, **kwargs):
    """
    Add ``injected`` to ``survey``, run brick, and saves ``injected``.

    Wraps :func:`legacypipe.runbrick.run_brick`.

    Parameters
    ----------
    opt : Namespace
        Command line options for :mod:`legacysim.runbrick`.

    survey : LegacySurveySim instance
        Survey, without ``injected``.

    kwargs : dict, default={}
        Arguments for ``legacypipe.runbrick.run_brick()`` following::

            run_brick(brickname, survey, **kwargs)

    Returns
    -------
    toret : dict
        Dictionary returned by :func:`legacypipe.runbrick.run_brick`.
    """
    injected_fn = survey.find_file('injected',brick=opt.brick,output=True)

    def write_injected(injected,header):
        header.add_record(dict(name='PRODTYPE',value='injected',comment='DESI data product type'))
        injected.writeto(injected_fn,primheader=header)

    if opt.forceall or 'injected' in opt.force or not os.path.isfile(injected_fn):
        # legacypipe-only run if opt.skipid == 0 and random filename not provided
        if (not (opt.skipid > 0)) and (opt.injected_fn is None):
            survey.injected = SimCatalog()
            survey.injected.collided = survey.injected.falses()
            if opt.sim_blobs:
                survey.injected.writeto(injected_fn)
                return NothingToDoError('Fitting blobs without input catalog: escaping.')
            toret = runbrick.run_brick(opt.brick, survey, **kwargs)
            # save empty injected catalog with versions in header
            write_injected(survey.injected,toret['version_header'])
            return toret

        if opt.skipid > 0:
            from legacysim import find_file
            kwargs_simid = {**survey.kwargs_simid,**{'skipid':opt.skipid-1}}
            fn = find_file(base_dir=survey.output_dir,filetype='injected',brickname=opt.brick,source='legacysim',**kwargs_simid)
            injected = SimCatalog(fn)
            injected.cut(injected.collided)
        else:
            injected = SimCatalog(opt.injected_fn)
            injected.fill_legacysim(survey=survey,seed=opt.seed)
            injected.cut(injected.brickname == opt.brick)
            if opt.nobj >= 0:
                injected = injected[opt.rowstart:opt.rowstart+opt.nobj]
                logger.info('Cutting to nobj = %d',opt.nobj)
        logger.info('SimCatalog size = %d',len(injected))

        if opt.col_radius > 0.:
            injected.collided = injected.mask_collisions(radius_in_degree=opt.col_radius/3600.)
        else:
            logger.info('Ignore collisions.')
            injected.collided = injected.falses()
    else:
        injected = SimCatalog(injected_fn)

    ncollided = injected.collided.sum()
    mask_injected = ~injected.collided

    if ncollided > 0:
        logger.info('Found %d collisions! You will have to run runbrick.py with --skipid = %d.',ncollided,opt.skipid+1)

    survey.injected = injected[mask_injected]

    if opt.sim_blobs:
        if not len(survey.injected):
            injected.writeto(injected_fn)
            return NothingToDoError('Fitting blobs with empty input catalog: escaping.')
        logger.info('Fitting blobs of input catalog.')
        blobradec = np.array([survey.injected.ra,survey.injected.dec]).T
        kwargs.update(blobradec=blobradec)

    toret = runbrick.run_brick(opt.brick, survey, **kwargs)
    injected[mask_injected] = survey.injected

    write_injected(injected,toret['version_header'])

    return toret


def set_brick(opt):
    """
    If no brick name provided in ``opt`` (``opt.radec == None``), build it from ra, dec and update ``opt.brick``.

    Copy-pasted from :func:`legacypipe.runbrick.run_brick`.

    Parameters
    ----------
    opt : argparse.Namespace
        Command-line arguments.
    """
    if opt.brick is not None:
        return
    ra,dec = opt.radec
    try:
        ra = float(ra)
    except:
        from astrometry.util.starutil_numpy import hmsstring2ra
        ra = hmsstring2ra(ra)
    try:
        dec = float(dec)
    except:
        from astrometry.util.starutil_numpy import dmsstring2dec
        dec = dmsstring2dec(dec)
    opt.brick = 'custom-%06i%s%05i' % (int(1000*ra), 'm' if dec < 0 else 'p', int(1000*np.abs(dec)))


def main(args=None):
    """
    Main routine which parses the optional inputs.

    Essentially copy-paste from :func:`legacypipe.runbrick.main`, main changes::

        parser = get_parser()
        survey, kwargs = get_runbrick_kwargs(**optdict)
        run_brick(opt.brick, survey, **kwargs)

    to::

        parser, args_runbrick = get_parser()
        survey, kwargs = get_runbrick_kwargs(args_runbrick,**optdict)
        run_brick(opt, survey, **kwargs)

    Parameters
    ----------
    args : list, default=None
        To overload command line arguments.
    """
    setup_logging('info')

    args = utils.get_parser_args(args=args)
    if args is None:
        logger.info('command-line args: %s',sys.argv)
    else:
        logger.info('args: %s',args)

    parser, args_runbrick = get_parser()
    opt = parser.parse_args(args=args)
    optdict = vars(opt)
    ps_fn = optdict.pop('ps', False)
    ps_t0 = optdict.pop('ps_t0', 0)
    verbose = optdict.pop('verbose')
    write_log = optdict.pop('write_log', None)

    if opt.brick is None and opt.radec is None:
        parser.print_help()
        return -1

    if opt.brick is not None and opt.radec is not None:
        print('Only ONE of --brick and --radec may be specified.')
        return -1

    # impacts optdict as well
    set_brick(opt)

    with MonkeyPatching() as mp:

        mp.add(legacypipe.survey,'get_version_header',
                wrapper_get_version_header(legacypipe.survey.get_version_header))
        mp.add(legacypipe.survey,'get_dependency_versions',
                wrapper_get_dependency_versions(legacypipe.survey.get_dependency_versions))
        mp.add(runbrick,'_add_stage_version',
                wrapper_add_stage_version(runbrick._add_stage_version))

        with EnvironmentManager(fn=opt.env_header,skip=opt.env_header is None):

            survey, kwargs = get_runbrick_kwargs(args_runbrick,**optdict)

            if write_log and not isinstance(write_log,str):
                write_log = survey.find_file('log',brick=opt.brick,output=True)
            if verbose == 0:
                level = logging.INFO
            else:
                level = logging.DEBUG

            setup_logging(level,filename=write_log)
            # tractor logging is *soooo* chatty
            logging.getLogger('tractor.engine').setLevel(level + 10)

            if kwargs in [-1, 0]:
                return kwargs
            kwargs.update(command_line=' '.join(sys.argv))

            if opt.plots:
                if opt.plot_base is not None:
                    utils.mkdir(os.path.dirname(opt.plot_base))
                import matplotlib
                matplotlib.use('Agg')
                import pylab as plt
                plt.figure(figsize=(12,9))
                plt.subplots_adjust(left=0.07, right=0.99, bottom=0.07, top=0.93,
                                    hspace=0.2, wspace=0.05)

            if ps_fn:
                if not isinstance(ps_fn,str): ps_fn = survey.find_file('ps',brick=opt.brick,output=True)
                utils.mkdir(os.path.dirname(ps_fn))
                import threading
                from collections import deque
                from legacypipe.utils import run_ps_thread
                ps_shutdown = threading.Event()
                ps_queue = deque()

                def record_event(msg):
                    from time import time
                    ps_queue.append((time(), msg))

                kwargs.update(record_event=record_event)
                if ps_t0 > 0:
                    record_event('start')

                ps_thread = threading.Thread(
                    target=run_ps_thread,
                    args=(os.getpid(), os.getppid(), ps_fn, ps_shutdown, ps_queue),
                    name='run_ps')
                ps_thread.daemon = True
                logger.info('Starting thread to run "ps"')
                ps_thread.start()

            logger.debug('kwargs: %s',kwargs)

            toret = -1
            try:
                run_brick(opt, survey, **kwargs)
                toret = 0
            except NothingToDoError as e:
                if hasattr(e, 'message'):
                    logger.info(e.message)
                else:
                    logger.info(e)
                toret = 0
            except RunbrickError as e:
                if hasattr(e, 'message'):
                    logger.info(e.message)
                else:
                    logger.info(e)
                toret = -1

            if ps_fn:
                # Try to shut down ps thread gracefully
                ps_shutdown.set()
                logger.info('Attempting to join the ps thread...')
                ps_thread.join(1.0)
                if ps_thread.isAlive():
                    logger.info('ps thread is still alive.')

    return toret


if __name__ == '__main__':

    from astrometry.util.ttime import Time,CpuMeas,MemMeas
    Time.add_measurement(CpuMeas)
    Time.add_measurement(MemMeas)
    import time
    setup_logging('info')
    logger.info('runbrick.py started at %s',time.strftime("%Y-%m-%d %H:%M:%S"))
    main()
    logger.info('runbrick.py finished at %s',time.strftime("%Y-%m-%d %H:%M:%S"))
