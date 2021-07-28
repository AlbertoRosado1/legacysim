"""
Script to produce image cutouts.

For details, run::

    python cutout.py --help

"""

import os
import argparse
import logging

import numpy as np
from matplotlib import pyplot as plt

from legacysim import RunCatalog, find_file, utils, setup_logging
from legacysim.analysis import ImageAnalysis


logger = logging.getLogger('legacysim.cutout')


def main(args=None):
    """Plot cutouts of sources."""
    parser = argparse.ArgumentParser(description=main.__doc__,formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--injected-id', nargs='*', type=int, default=None,
                        help='ids of sources injected by legacysim to plot')
    parser.add_argument('--obj-id', nargs='*', type=int, default=None,
                        help='ids of detected sources to plot')
    parser.add_argument('--ncuts', type=int, default=0,
                        help='Pick sources injected by legacysim with a source detected by legacypipe nearby. Maximum number of cutouts for each brick run')
    parser.add_argument('--boxsize', type=int, default=None, help='Cutout size in pixels')
    plot_base_template = 'cutout-%(brickname)s-%(iobj)d.png'
    parser.add_argument('--plot-fn', type=str, default=None, help='Plot file name; \
                        defaults to coadd-dir/%s' % plot_base_template.replace('%','%%'))
    RunCatalog.get_output_parser(parser=parser,add_source=True)
    opt = parser.parse_args(args=utils.get_parser_args(args))
    runcat = RunCatalog.from_output_cmdline(opt)

    def plot_cutout(image, run, filetypes, slices, islices=None):
        if islices is None:
            islices = list(range(1,len(slices)+1))
        for islice,(slicex,slicey) in zip(islices,slices):
            fig,lax = plt.subplots(ncols=len(filetypes),sharex=False,sharey=False,figsize=(4*len(filetypes),4),squeeze=False)
            fig.subplots_adjust(hspace=0.2,wspace=0.2)
            for ax,filetype in zip(lax[0],filetypes):
                image.read_image(filetype=filetype)
                image.set_subimage(slicex,slicey)
                image.plot(ax)
                image.plot_sources(ax)
            plot_fn_kwargs = {'brickname':run.brickname,'iobj':islice}
            if opt.plot_fn is None:
                image_fn = find_file(base_dir=opt.output_dir,filetype='image-jpeg',brickname=run.brickname,source=opt.source,**run.kwargs_simid)
                plot_fn = os.path.join(os.path.dirname(image_fn),plot_base_template % plot_fn_kwargs)
                if plot_fn == image_fn:
                    raise ValueError('Cutout filename is the same as image: %s' % image_fn)
            else:
                plot_fn = opt.plot_fn % plot_fn_kwargs
            utils.savefig(fn=plot_fn)

    for run in runcat:

        image = ImageAnalysis(base_dir=opt.output_dir,brickname=run.brickname,kwargs_simid=run.kwargs_simid,source=opt.source)
        filetypes = ['image-jpeg','model-jpeg','resid-jpeg']

        if opt.injected_id is not None:
            image.read_image(filetype=filetypes[0])
            image.read_image_wcs()
            image.read_sources(filetype='injected')
            image.sources.cut(np.isin(image.sources.id,opt.injected_id))
            slices = image.get_zooms(boxsize_in_pixels=opt.boxsize)
            plot_cutout(image,run,filetypes,slices,islices=image.sources.id)

        if opt.obj_id is not None:
            image.read_image(filetype=filetypes[0])
            image.read_image_wcs()
            image.read_sources(filetype='tractor')
            image.sources.cut(np.isin(image.sources.objid,opt.obj_id))
            slices = image.get_zooms(boxsize_in_pixels=opt.boxsize)
            plot_cutout(image,run,filetypes,slices,islices=image.sources.objid)

        if opt.ncuts != 0:
            image.read_image(filetype=filetypes[0])
            image.read_image_wcs()
            image.read_sources(filetype='injected')
            slices,islices = image.suggest_zooms(boxsize_in_pixels=opt.boxsize)
            if hasattr(image.sources,'id'): islices = image.sources.id
            elif hasattr(image.sources,'objid'): islices = image.sources.objid
            if opt.ncuts >= 0:
                slices = slices[:opt.ncuts]
                islices = islices[:opt.ncuts]
            plot_cutout(image,run,filetypes,slices,islices)


if __name__ == '__main__':

    setup_logging()
    main()
