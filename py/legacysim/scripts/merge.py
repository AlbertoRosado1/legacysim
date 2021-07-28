"""
Script to merge catalogs of different bricks/runs together.

For details, run::

    python merge.py --help

"""

import os
import argparse
import logging

from legacysim import RunCatalog, utils, setup_logging
from legacysim.analysis import CatalogMerging


logger = logging.getLogger('legacysim.merge')


def main(args=None):
    """Merge catalogs."""
    parser = argparse.ArgumentParser(description=main.__doc__,formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--cat-dir', type=str, default='.', help='Directory for merged catalogs')
    cat_base_template = 'merged_%(filetype)s.fits'
    cat_legacypipe_base_template = 'merged_%(filetype)s_legacypipe.fits'
    parser.add_argument('--cat-fn', type=str, default=None,
                        help='Output file name. If not provided, defaults to cat-dir/%s if source is legacypipe, \
                        else cat-dir/%s.' % (cat_legacypipe_base_template.replace('%','%%'),cat_base_template.replace('%','%%')))
    RunCatalog.get_output_parser(parser=parser,add_source=True,add_filetype=True)
    opt = parser.parse_args(args=utils.get_parser_args(args))
    RunCatalog.set_default_output_cmdline(opt)
    runcat = RunCatalog.from_output_cmdline(opt)
    if opt.cat_fn is None:
        opt.cat_fn = os.path.join(opt.cat_dir,(cat_legacypipe_base_template if opt.source == 'legacypipe' else cat_base_template) % {'filetype':opt.filetype})
    merge = CatalogMerging(base_dir=opt.output_dir,runcat=runcat,source=opt.source)
    #for field in runcat.fields: print(field,runcat.get(field))
    merge.merge(opt.filetype,cat_fn=opt.cat_fn,write=True)


if __name__ == '__main__':

    setup_logging()
    main()
