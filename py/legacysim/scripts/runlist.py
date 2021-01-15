"""
Script to write run list (eventually accounting for module versions), useful when scheduling jobs.

For details, run::

    python runlist.py --help

"""

import argparse
import logging

from legacysim import RunCatalog, get_sim_id, utils, setup_logging
from legacysim.batch import EnvironmentManager


logger = logging.getLogger('legacysim.runlist')


def main(args=None,force_write=False):

    parser = argparse.ArgumentParser(description='RunList',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    runlist_template = 'runlist.txt'
    for key in get_sim_id.keys():
        parser.add_argument('--%s-out' % key, nargs='*', type=int, default=None, help='Write these %ss in run list.' % key)
    parser.add_argument('--modules', nargs='*', type=str, default=[], help='Read version of these modules in file headers (if files exist).')
    parser.add_argument('--write-list', nargs='?', type=str, default=False, const=True,
                        help='Write missing run list to file name. If file name is not provided, defaults to %s.' % runlist_template
                         + ' This run list can be used to instantiate RunCatalog through RunCatalog.from_list(), in order to iterate easily through the runs.')
    RunCatalog.get_output_parser(parser=parser,add_source=True)
    utils.get_parser_action_by_dest(parser,'source').default = 'legacypipe'
    opt = parser.parse_args(args=utils.get_parser_args(args))
    # if script called from command-line, write list; else, write only if --write-list is provided
    if force_write and not opt.write_list:
        opt.write_list = True

    runcat = RunCatalog.from_output_cmdline(opt)
    if runcat.size == 0:
        logger.warning('No run found.')
        return None

    level = logging.root.level
    setup_logging('warning')
    if opt.modules:
        for irun,run in enumerate(runcat):
            environment = EnvironmentManager(base_dir=opt.output_dir,brickname=run.brickname,source=opt.source,kwargs_simid=run.kwargs_simid)
            istages = runcat.append_stages(environment.get_stages_versions(opt.modules))
            runcat.stagesid[irun] = istages
    setup_logging(level)
    # replace old ranids with new ones, if not None
    kwargs_simids = {key:getattr(opt,'%s_out' % key) for key in get_sim_id.keys()}
    if not all(val is None for val in kwargs_simids.values()):
        kwargs_simids = runcat.kwargs_simids_from_cmdline({key:getattr(opt,'%s_out' % key) for key in get_sim_id.keys()})
        runcat.replace_sim_id(kwargs_simids=kwargs_simids)
    runcat.remove_duplicates().update_stages()

    if opt.write_list:
        if not isinstance(opt.write_list,str):
            opt.write_list = runlist_template
        runcat.write_list(opt.write_list)

    return runcat


if __name__ == '__main__':

    setup_logging()
    main(force_write=True)
