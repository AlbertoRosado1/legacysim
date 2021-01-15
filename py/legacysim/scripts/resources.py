"""
Script to plot cpu and memory usage.

For details, run::

    python resources.py --help

"""

import argparse
import logging

from matplotlib import pyplot as plt

from legacysim import RunCatalog,find_file,setup_logging,utils
from legacysim.analysis import ResourceAnalysis


logger = logging.getLogger('resources')


def main(args=None):

    parser = argparse.ArgumentParser(description='Resources',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--do', type=str, choices=['single','summary'], default='summary',
                        help='Pass "single" for a time series for each run; "summary" for summary statistics of all runs')
    plot_summary_base = 'resources-summary.png'
    parser.add_argument('--plot-fn', type=str, default=None, help='Plot filename; \
                        if --do single, defaults to ps-filename + .png; \
                        else (--do summary), defaults to %s' % plot_summary_base)
    RunCatalog.get_output_parser(parser=parser)
    opt = parser.parse_args(args=utils.get_parser_args(args))
    runcat = RunCatalog.from_output_cmdline(opt)

    if opt.do == 'single':
        for run in runcat:
            resource = ResourceAnalysis(base_dir=opt.output_dir,bricknames=run.brickname,source='legacysim',kwargs_files=run.kwargs_file)
            if opt.plot_fn is None:
                plot_fn = find_file(base_dir=opt.output_dir,filetype='ps',brickname=run.brickname,source='legacysim',**run.kwargs_file)
                plot_fn = plot_fn[:-len('.fits')] + '.png'
            else: plot_fn = opt.plot_fn % {**{'outdir':opt.output_dir,'brick':run.brickname},**run.kwargs_file}
            resource.set_catalog(name='series',filetype='ps')
            if resource.series == 0:
                logger.info('No ps file for brick %s, %s; skipping.',run.brickname,run.kwargs_file)
            else:
                resource.plot_one_series(fn=plot_fn)

    if opt.do == 'summary':
        if opt.plot_fn is None: opt.plot_fn = plot_summary_base
        resource = ResourceAnalysis(base_dir=opt.output_dir,runcat=runcat)
        fig,lax = plt.subplots(ncols=2,sharex=False,sharey=False,figsize=(12,4))
        fig.subplots_adjust(hspace=0.2,wspace=0.2)
        lax = lax.flatten()
        resource.plot_bar(ax=lax[0])
        resource.plot_all_series(ax=lax[1])
        utils.savefig(fn=opt.plot_fn)


if __name__ == '__main__':

    setup_logging()
    main()
