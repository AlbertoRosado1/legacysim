"""
Script to check all runs have completed by verifying all files exist on disk (and optionally can be opened).

For details, run::

    python check.py --help

"""

import argparse
import logging

from astrometry.util.file import unpickle_from_file

from legacysim import SimCatalog, RunCatalog, find_file, get_sim_id, utils, setup_logging


logger = logging.getLogger('legacysim.check')


def main(args=None):

    parser = argparse.ArgumentParser(description='Check',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--read', action='store_true', default=False,
                        help='Try read file from disk?')
    runlist_template = 'runlist.txt'
    parser.add_argument('--write-list', nargs='?', type=str, default=False, const=True,
                        help='Write missing run list to file name. If file name is not provided, defaults to %s.' % runlist_template
                         + ' This run list can be used to instantiate RunCatalog through RunCatalog.from_list(), in order to iterate easily through the runs.')
    parser = RunCatalog.get_output_parser(parser=parser,add_stages=True,add_filetype=True,add_source=True)
    opt = parser.parse_args(args=utils.get_parser_args(args))
    for key,default in zip(get_sim_id.keys(),get_sim_id.default()):
        if getattr(opt,key,None) is None: setattr(opt,key,[default])
    runinput = RunCatalog.from_input_cmdline(opt)
    RunCatalog.set_default_output_cmdline(opt)
    runoutput = RunCatalog.from_output_cmdline(opt,force_from_disk=True)
    if opt.read:
        mask = runoutput.trues()
        msg = 'File %s exists but yields OSError.'
        for irun,run in enumerate(runoutput):
            if opt.filetype == 'pickle' and opt.pickle_pat is not None:
                fn = opt.pickle_pat % dict(brick=run.brickname,ranid=get_sim_id(**run.kwargs_simid)) % run.stages[-1]
            else:
                fn = find_file(base_dir=opt.output_dir,filetype=opt.filetype,brickname=run.brickname,
                                source=opt.source,stage=run.stages.keys()[-1],**run.kwargs_simid)
            try:
                if opt.filetype == 'pickle':
                    unpickle_from_file(fn)
                else:
                    SimCatalog(fn)
            except OSError:
                logger.info(msg,fn)
                mask[irun] = False
        runoutput = runoutput[mask]

    mask = runinput.isin(runoutput,ignore_stage_version=True)
    # remove runs without injected sources.
    if opt.source == 'legacysim':
        for irun,run in enumerate(runinput):
            if not mask[irun]:
                fn = find_file(opt.output_dir,'injected',brickname=run.brickname,source=opt.source,**run.kwargs_simid)
                try:
                    injected = SimCatalog(fn)
                    if injected.size == 0: mask[irun] = True
                except OSError:
                    pass

    runinput = runinput[~mask]
    if mask.all():
        logger.info('All runs in output!')
    else:
        logger.info('%d runs missing.',runinput.size)
        for run in runinput:
            txt = ' '.join(['%s:%s' % (field,run.get(field)) for field in runinput.fields])
            logger.info('Run %s missing.',txt)
        if opt.write_list:
            if not isinstance(opt.write_list,str):
                opt.write_list = runlist_template
            runinput.write_list(opt.write_list)

    return runinput


if __name__ == '__main__':

    setup_logging()
    main()
