import os
import logging
import shutil

import numpy as np
import fitsio
from legacypipe.catalog import read_fits_catalog
from tractor.basics import PointSource
from tractor.galaxy import DevGalaxy
from tractor.sersic import SersicGalaxy
from legacypipe import runbrick as lprunbrick
from legacypipe.survey import wcs_for_brick

from obiwan import setup_logging,LegacySurveySim,find_file,SimCatalog,BrickCatalog,runbrick,utils
from obiwan.batch import EnvironmentManager


logger = logging.getLogger('obiwan.test_runbrick')


setup_logging()


def generate_randoms(brickname, zoom=(0,3600,0,3600), zoom_margin=5, mag_range=(19.,20.), shape_r_range=(0.,1.), size=2, seed=42):

    brick = BrickCatalog().get_by_name(brickname)
    wcs = wcs_for_brick(brick)
    (x0,x1,y0,y1) = zoom
    W = x1-x0-2*zoom_margin
    H = y1-y0-2*zoom_margin
    assert (W>0) and (H>0)
    targetwcs = wcs.get_subimage(x0+zoom_margin, y0+zoom_margin, W, H)
    radecbox = np.ravel([targetwcs.pixelxy2radec(x,y) for x,y in [(1,1),(W,H)]],order='F')
    radecbox = np.concatenate([np.sort(radecbox[:2]),np.sort(radecbox[2:])])
    randoms = SimCatalog(size=size)
    rng = np.random.RandomState(seed=seed)
    randoms.ra,randoms.dec = utils.sample_ra_dec(radecbox=radecbox,size=randoms.size,rng=rng)
    randoms.bx,randoms.by = brick.get_xy_from_radec(randoms.ra,randoms.dec)
    flux_range = utils.mag2nano(mag_range)
    for b in ['g','r','z']:
        randoms.set('flux_%s' % b,rng.uniform(*flux_range,size=randoms.size))
    randoms.sersic = randoms.full(4)
    ba = rng.uniform(0.2,1.,size=randoms.size)
    phi = rng.uniform(0,np.pi,size=randoms.size)
    randoms.shape_e1,randoms.shape_e2 = utils.get_shape_e1_e2(ba,phi)
    randoms.shape_r = rng.uniform(*shape_r_range,size=randoms.size)
    randoms.brickname = randoms.full(brickname)

    return randoms


def test_eq_legacypipe():

    survey_dir = os.path.join(os.path.dirname(__file__), 'testcase3')
    output_dir = 'out-testcase3-obiwan'
    legacypipe_dir = 'out-testcase3-legacypipe'
    os.environ['GAIA_CAT_DIR'] = os.path.join(survey_dir, 'gaia')
    os.environ['GAIA_CAT_VER'] = '2'
    brickname = '2447p120'
    zoom = [1020,1070,2775,2815]

    lprunbrick.main(args=['--brick', brickname, '--zoom', *map(str,zoom),
                        '--no-wise', '--force-all', '--no-write',
                        '--survey-dir', survey_dir,
                        '--outdir', legacypipe_dir,
                        '--force-all',
                        '--threads', '1'])

    runbrick.main(args=['--brick', brickname, '--zoom', *map(str,zoom),
                        '--no-wise', '--force-all', '--no-write',
                        '--survey-dir', survey_dir,
                        '--outdir', output_dir,
                        '--force-all',
                        '--threads', 1])

    legacypipe_fn = find_file(base_dir=legacypipe_dir,filetype='tractor',source='legacypipe',brickname=brickname)
    tractor_legacypipe = SimCatalog(legacypipe_fn)
    obiwan_fn = find_file(base_dir=output_dir,filetype='tractor',source='obiwan',brickname=brickname)
    tractor_obiwan = SimCatalog(obiwan_fn)
    assert tractor_obiwan == tractor_legacypipe

    # check header
    header_legacypipe = fitsio.read_header(legacypipe_fn)
    header_obiwan = fitsio.read_header(obiwan_fn)
    header_randoms = fitsio.read_header(find_file(base_dir=output_dir,filetype='randoms',brickname=brickname))
    #assert len(header_obiwan) == len(header_randoms)
    for key in header_randoms:
        if key != 'PRODTYPE':
            assert header_obiwan[key] == header_randoms[key]
    assert 'OBIWANV' in header_obiwan
    assert 'galsim' in [header_obiwan[key] for key in header_obiwan]
    stages = [val for key,val in EnvironmentManager.shorts_stage.items() if key != 'wise_forced']
    for stage in stages:
        assert ('OBV_%s' % stage) in header_obiwan
    # Obiwan: version + comment (2), galsim (2) and OBV
    assert len(header_obiwan) == len(header_legacypipe) + 2 + 2 + len(stages)


def test_simblobs():

    survey_dir = os.path.join(os.path.dirname(__file__), 'testcase3')
    output_dir = 'out-testcase3-obiwan'
    os.environ['GAIA_CAT_DIR'] = os.path.join(survey_dir, 'gaia')
    os.environ['GAIA_CAT_VER'] = '2'
    randoms_fn = os.path.join(output_dir,'input_randoms.fits')
    brickname = '2447p120'
    zoom = [1020,1070,2775,2815]
    randoms = generate_randoms(brickname,zoom=[1020,1070,2785,2815],mag_range=[19.,20.],shape_r_range=[0.,0.])
    randoms.writeto(randoms_fn)

    runbrick.main(args=['--brick', brickname, '--zoom', *map(str,zoom),
                        '--no-wise', '--force-all', '--no-write',
                        '--survey-dir', survey_dir,
                        '--ran-fn', randoms_fn,
                        '--outdir', output_dir,
                        '--threads',1])

    runbrick.main(args=['--brick', brickname, '--zoom', *map(str,zoom),
                        '--no-wise', '--force-all', '--no-write',
                        '--survey-dir', survey_dir,
                        '--ran-fn', randoms_fn,
                        '--outdir', output_dir,
                        '--fileid', 1,
                        '--sim-blobs',
                        '--threads', 1])

    tractor_simblobs = SimCatalog(find_file(base_dir=output_dir,filetype='tractor',source='obiwan',brickname=brickname,fileid=1))
    indin = randoms.match_radec(tractor_simblobs,radius_in_degree=0.05/3600.,nearest=True)[0]
    assert indin.size == randoms.size

    tractor_all = SimCatalog(find_file(base_dir=output_dir,filetype='tractor',source='obiwan',brickname=brickname))
    indin = tractor_all.match_radec(tractor_simblobs,radius_in_degree=0.001/3600.,nearest=True,return_distance=True)[0]
    assert indin.size == tractor_simblobs.size


def test_case3():

    survey_dir = os.path.join(os.path.dirname(__file__), 'testcase3')
    output_dir = 'out-testcase3-obiwan'
    os.environ['GAIA_CAT_DIR'] = os.path.join(survey_dir, 'gaia')
    os.environ['GAIA_CAT_VER'] = '2'
    checkpoint_fn = os.path.join(output_dir, 'checkpoint.pickle')
    if os.path.exists(checkpoint_fn):
        os.unlink(checkpoint_fn)
    randoms_fn = os.path.join(output_dir,'input_randoms.fits')
    brickname = '2447p120'
    zoom = [1020,1070,2775,2815]
    randoms = generate_randoms(brickname,zoom=[1020,1070,2785,2815],mag_range=[19.,20.],shape_r_range=[0.,0.])
    randoms.writeto(randoms_fn)

    for extra_args in [['--plots','--plot-base',os.path.join(output_dir,'brick-%(brick)s')],
                    ['--sim-stamp','tractor'],['--sim-stamp','galsim'],
                    ['--sim-stamp','tractor','--add-sim-noise','gaussian'],
                    ['--sim-stamp','tractor','--add-sim-noise','poisson'],
                    ['--sim-stamp','galsim','--add-sim-noise','gaussian'],
                    ['--sim-stamp','galsim','--add-sim-noise','poisson'],
                    ['--sim-stamp','galsim','--add-sim-noise','gaussian','--nobj',0],
                    ['--sim-stamp','galsim','--add-sim-noise','gaussian','--nobj',1],
                    ['--sim-stamp','galsim','--add-sim-noise','gaussian','--rowstart',1,'--nobj',1],
                    ['--sim-stamp','tractor','--col-radius',3600.]
                    ]:

        runbrick.main(args=['--brick', brickname, '--zoom', *map(str,zoom),
                            '--no-wise', '--force-all', '--no-write',
                            '--survey-dir', survey_dir,
                            '--ran-fn', randoms_fn,
                            '--outdir', output_dir,
                            '--seed', 42,
                            '--threads', 1] + extra_args)

        # build-up truth
        origin_ra = [244.77973,244.77828]
        origin_dec = [12.07234,12.07250]
        origin_type = [(DevGalaxy,SersicGalaxy),(PointSource,)]
        randoms = SimCatalog(randoms_fn)
        rowstart,nobj = 0,len(randoms)
        if '--rowstart' in extra_args: rowstart = extra_args[extra_args.index('--rowstart')+1]
        if '--nobj' in extra_args: nobj = extra_args[extra_args.index('--nobj')+1]
        randoms = randoms[rowstart:rowstart+nobj]
        col_radius = 5.
        if '--col-radius' in extra_args: col_radius = extra_args[extra_args.index('--col-radius')+1]
        collided = randoms.mask_collisions(radius_in_degree=col_radius/3600.)
        randoms = randoms[~collided]
        ra,dec = np.concatenate([origin_ra,randoms.ra]),np.concatenate([origin_dec,randoms.dec])

        nsigmas = 30 # max tolerance
        survey = LegacySurveySim(output_dir=output_dir,kwargs_file={'rowstart':rowstart})
        fn = survey.find_file('tractor',brick=brickname,output=True)
        logger.info('Reading %s',fn)
        tractor = SimCatalog(fn)

        # first match ra,dec
        assert len(tractor) == len(origin_ra) + len(randoms), 'Found %d objects, injected %d sources' % (len(tractor),len(origin_ra) + len(randoms))
        # first match ra,dec
        indin,indout,distance = utils.match_radec(ra,dec,tractor.ra,tractor.dec,radius_in_degree=0.05/3600.,nearest=True,return_distance=True)
        assert len(indin) == len(tractor), 'Matched %d objects among %d sources' % (len(indin),len(tractor)) # all matches
        indout = indout[np.argsort(indin)]
        tractor_all = tractor[indout] # reorder such that len(origin_ra): are injected sources
        # ra,dec tolerance
        sigma = np.sqrt(((tractor_all.ra-ra)**2*tractor_all.ra_ivar + (tractor_all.dec-dec)**2*tractor_all.dec_ivar)/2.)
        logger.info('Max angular distance is %.4f arcsec, %.4f sigmas',distance.max()*3600.,sigma.max())
        assert np.all(sigma < nsigmas)
        # flux tolerance
        tractor = tractor_all[len(origin_ra):]
        if tractor.size:
            for b in ['g','r','z']:
                diff = np.abs(tractor.get('flux_%s' % b) - randoms.get('flux_%s' % b))
                sigma = diff*np.sqrt(tractor.get('flux_ivar_%s' % b))
                logger.info('Max flux diff in %s band is %.4f, %.4f sigmas',b,diff.max(),sigma.max())
                assert np.all(sigma < nsigmas)

        cat = read_fits_catalog(tractor_all)
        logger.info('Read catalog: %s',cat)
        assert len(cat) == len(tractor_all)
        # check origin sources are of the correct type
        for isrc,src in enumerate(cat[:len(origin_ra)]):
            assert type(src) in origin_type[isrc]

        # check injected sources are of the correct type
        for isrc,src in enumerate(cat[len(origin_ra):]):
            assert type(src) is PointSource


def test_case3_shape():

    survey_dir = os.path.join(os.path.dirname(__file__), 'testcase3')
    output_dir = 'out-testcase3-obiwan-shape'
    os.environ['GAIA_CAT_DIR'] = os.path.join(survey_dir, 'gaia')
    os.environ['GAIA_CAT_VER'] = '2'
    checkpoint_fn = os.path.join(output_dir, 'checkpoint.pickle')
    if os.path.exists(checkpoint_fn):
        os.unlink(checkpoint_fn)
    randoms_fn = os.path.join(output_dir,'input_randoms.fits')
    log_fn = os.path.join(output_dir,'log.out')
    brickname = '2447p120'
    zoom = [1020,1070,2775,2815]
    randoms = generate_randoms(brickname,zoom=[1020,1040,2785,2815], zoom_margin=5, mag_range=[19.,20.], size=1)
    randoms.shape_r = randoms.full(2.)
    randoms.writeto(randoms_fn)

    for extra_args in [['--plots','--plot-base',os.path.join(output_dir,'brick-%(brick)s')],
                    ['--sim-stamp','tractor'],['--sim-stamp','galsim'],
                    ['--sim-stamp','tractor','--add-sim-noise','gaussian'],
                    ['--sim-stamp','galsim','--add-sim-noise','poisson']
                    ]:

        runbrick.main(args=['--brick', brickname, '--zoom', *map(str,zoom),
                            '--no-wise', '--force-all', '--no-write',
                            '--survey-dir', survey_dir,
                            '--ran-fn', randoms_fn,
                            '--outdir', output_dir,
                            '--seed', 42,
                            '--threads', 2,
                            '--verbose', '--log-fn', log_fn] + extra_args)

        setup_logging(logging.INFO)

        # input randoms
        randoms = SimCatalog(randoms_fn)
        col_radius = 5.
        if '--col-radius' in extra_args: col_radius = extra_args[extra_args.index('--cl-radius')+1]
        collided = randoms.mask_collisions(radius_in_degree=col_radius/3600.)
        randoms = randoms[~collided]

        # build-up truth
        origin_ra = [244.77973,244.77828]
        origin_dec = [12.07234,12.07250]
        origin_type = [(DevGalaxy,SersicGalaxy),(PointSource,)]
        ra,dec = np.concatenate([origin_ra,randoms.ra]),np.concatenate([origin_dec,randoms.dec])

        nsigmas = 80 # max tolerance
        survey = LegacySurveySim(output_dir=output_dir)
        fn = survey.find_file('tractor',brick=brickname,output=True)
        logger.info('Reading %s',fn)
        tractor = SimCatalog(fn)

        assert len(tractor) == len(origin_ra) + len(randoms), 'Found %d objects, injected %d sources' % (len(tractor),len(origin_ra) + len(randoms))
        # first match ra,dec
        indin,indout,distance = utils.match_radec(ra,dec,tractor.ra,tractor.dec,radius_in_degree=0.05/3600.,nearest=True,return_distance=True)
        assert len(indin) == len(tractor), 'Matched %d objects among %d sources' % (len(indin),len(tractor)) # all matches
        indout = indout[np.argsort(indin)]
        tractor_all = tractor[indout] # reorder such that len(origin_ra): are injected sources
        # ra,dec tolerance
        sigma = np.sqrt(((tractor_all.ra-ra)**2*tractor_all.ra_ivar + (tractor_all.dec-dec)**2*tractor_all.dec_ivar)/2.)
        logger.info('Max angular distance is %.4f arcsec, %.4f sigmas',distance.max()*3600.,sigma.max())
        assert np.all(sigma < nsigmas)
        # flux tolerance
        tractor = tractor_all[len(origin_ra):]
        for b in ['g','r','z']:
            diff = np.abs(tractor.get('flux_%s' % b) - randoms.get('flux_%s' % b))
            sigma = diff*np.sqrt(tractor.get('flux_ivar_%s' % b))
            logger.info('Max flux diff in %s band is %.4f, %.4f sigmas',b,diff.max(),sigma.max())
            assert np.all(sigma < nsigmas)

        for field in ['shape_e1','shape_e2','shape_r']:
            diff = np.abs(tractor.get(field) - randoms.get(field))
            sigma = diff*np.sqrt(tractor.get('%s_ivar' % field))
            logger.info('Max %s diff is %.4f, %.4f sigmas',field,diff.max(),sigma.max())
            assert np.all(sigma < nsigmas)

        cat = read_fits_catalog(tractor_all)
        logger.info('Read catalog: %s',cat)
        assert len(cat) == len(tractor_all)

        for isrc,src in enumerate(cat[:len(origin_ra)]):
            assert type(src) in origin_type[isrc]

        # check injected sources are of the correct type
        for isrc,src in enumerate(cat[len(origin_ra):]):
            assert type(src) is DevGalaxy or type(src) is SersicGalaxy


def test_mzlsbass2():

    survey_dir = os.path.join(os.path.dirname(__file__), 'mzlsbass2')
    output_dir = 'out-mzlsbass2-obiwan'
    os.environ['GAIA_CAT_DIR'] = os.path.join(survey_dir, 'gaia')
    os.environ['GAIA_CAT_VER'] = '2'

    randoms_fn = os.path.join(output_dir,'input_randoms.fits')
    log_fn = os.path.join(output_dir,'log.out')
    brickname = '1773p595'
    zoom = [1300,1500,700,900]
    #randoms = generate_randoms(brickname,zoom=zoom,zoom_margin=10)
    randoms = generate_randoms(brickname,zoom=[1300,1400,700,800],zoom_margin=10)
    randoms.writeto(randoms_fn)

    for extra_args in [['--plots','--plot-base',os.path.join(output_dir,'brick-%(brick)s')],
                    ['--sim-stamp','tractor','--add-sim-noise','gaussian'],
                    ['--sim-stamp','galsim','--add-sim-noise','poisson']
                    ]:

        runbrick.main(args=['--brick', brickname, '--zoom', *map(str,zoom),
                            '--no-wise', '--force-all', '--no-write',
                            '--survey-dir', survey_dir,
                            '--ran-fn', randoms_fn,
                            '--outdir', output_dir,
                            '--sim-blobs',
                            '--seed', 42,
                            '--verbose','--log-fn', log_fn] + extra_args)

        setup_logging(logging.INFO)

        # input randoms
        randoms = SimCatalog(randoms_fn)
        col_radius = 5.
        if '--col-radius' in extra_args: col_radius = extra_args[extra_args.index('--cl-radius')+1]
        collided = randoms.mask_collisions(radius_in_degree=col_radius/3600.)
        randoms = randoms[~collided]

        nsigmas = 30 # max tolerance
        survey = LegacySurveySim(output_dir=output_dir)
        fn = survey.find_file('tractor',brick=brickname,output=True)
        logger.info('Reading %s',fn)
        tractor = SimCatalog(fn)

        # first match ra,dec
        indin,indout,distance = randoms.match_radec(tractor,radius_in_degree=0.1/3600.,nearest=True,return_distance=True)
        assert len(indin) == len(randoms), 'Matched %d objects among %d injected sources' % (len(indin),len(randoms))
        indout = indout[np.argsort(indin)]
        tractor = tractor[indout] # reorder such that len(origin_ra): are injected sources
        # ra,dec tolerance
        sigma = np.sqrt(((tractor.ra-randoms.ra)**2*tractor.ra_ivar + (tractor.dec-randoms.dec)**2*tractor.dec_ivar)/2.)
        logger.info('Max angular distance is %.4f arcsec, %.4f sigmas',distance.max()*3600.,sigma.max())
        assert np.all(sigma < nsigmas)
        # flux tolerance
        for b in ['g','r','z']:
            diff = np.abs(tractor.get('flux_%s' % b) - randoms.get('flux_%s' % b))
            sigma = diff*np.sqrt(tractor.get('flux_ivar_%s' % b))
            logger.info('Max flux diff in %s band is %.4f, %.4f sigmas',b,diff.max(),sigma.max())
            assert np.all(sigma < nsigmas)


def test_rerun():

    survey_dir = os.path.join(os.path.dirname(__file__), 'testcase3')
    output_dirs = ['out-case3-obiwan-rerun-%d' % i for i in range(1,3)]
    os.environ['GAIA_CAT_DIR'] = os.path.join(survey_dir, 'gaia')
    os.environ['GAIA_CAT_VER'] = '2'
    for output_dir in output_dirs:
        checkpoint_fn = os.path.join(output_dir,'checkpoint.pickle')
        if os.path.exists(checkpoint_fn):
            os.unlink(checkpoint_fn)
    randoms_fn = os.path.join(output_dirs[0],'input_randoms.fits')
    brickname = '2447p120'
    zoom = [1020,1070,2775,2815]
    randoms = generate_randoms(brickname,zoom=[1020,1070,2785,2815],mag_range=[19.,20.],shape_r_range=[0.,0.],size=2)
    randoms.writeto(randoms_fn)

    for extra_args in [['--sim-stamp','tractor','--add-sim-noise','gaussian']
                    ]:

        common_args = ['--brick', brickname, '--zoom', *map(str,zoom),
                            '--no-wise',
                            '--survey-dir', survey_dir,
                            '--seed', 42,
                            '--threads', 1] + extra_args

        runbrick.main(args=common_args + ['--ran-fn',randoms_fn, '--force-all', '--no-write','--outdir', output_dirs[0]])

        fn = find_file(base_dir=output_dirs[0],filetype='tractor',brickname=brickname,source='obiwan')
        tractor_ref = SimCatalog(fn)

        for stages in [['outliers','writecat'],
                        ['refs','fitblobs','writecat']]:

            shutil.rmtree(output_dirs[1],ignore_errors=True)

            for istage,stage in enumerate(stages):

                args = common_args + ['--stage',stage,'--outdir',output_dirs[1]]
                if istage == 0:
                    args += ['--ran-fn',randoms_fn]
                runbrick.main(args=args)

            fn = find_file(base_dir=output_dirs[1],filetype='tractor',brickname=brickname,source='obiwan')
            tractor = SimCatalog(fn)

            assert tractor == tractor_ref


def test_skipid():

    survey_dir = os.path.join(os.path.dirname(__file__), 'testcase3')
    output_dir = 'out-case3-obiwan-skipid'
    os.environ['GAIA_CAT_DIR'] = os.path.join(survey_dir, 'gaia')
    os.environ['GAIA_CAT_VER'] = '2'
    checkpoint_fn = os.path.join(output_dir,'checkpoint.pickle')
    if os.path.exists(checkpoint_fn):
        os.unlink(checkpoint_fn)
    randoms_fn = os.path.join(output_dir,'input_randoms.fits')
    brickname = '2447p120'
    zoom = [1020,1070,2775,2815]
    randoms = generate_randoms(brickname,zoom=[1020,1070,2785,2815],mag_range=[19.,20.],shape_r_range=[0.,0.],size=2)
    randoms.writeto(randoms_fn)

    for extra_args in [['--col-radius', 3600],
                    ['--col-radius', -1],
                    ]:

        common_args = ['--brick', brickname, '--zoom', *map(str,zoom),
                            '--no-wise', '--no-write',
                            '--survey-dir', survey_dir,
                            '--outdir', output_dir,
                            '--seed', 42,
                            '--col-radius', 3600,
                            '--threads', 1] + extra_args

        runbrick.main(args=common_args + ['--force-all', '--ran-fn', randoms_fn])

        fn = find_file(base_dir=output_dir,filetype='randoms',brickname=brickname,source='obiwan')
        randoms_skip0 = SimCatalog(fn)

        if '--col-radius' in extra_args and extra_args[extra_args.index('--col-radius')-1] > 3000:
            assert (randoms_skip0.collided.sum() > 0) and (randoms_skip0.collided.sum() < randoms_skip0.size)

        runbrick.main(args=common_args + ['--skipid',1])
        fn = find_file(base_dir=output_dir,filetype='randoms',brickname=brickname,source='obiwan',skipid=1)
        randoms_skip1 = SimCatalog(fn)
        for field in ['ra','dec']:
            assert np.all(randoms_skip1.get(field) == randoms_skip0.get(field)[randoms_skip0.collided])
