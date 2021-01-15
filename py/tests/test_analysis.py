import os
import glob
import numpy as np

from matplotlib import pyplot as plt
from legacypipe import runbrick as lprunbrick

from legacysim import setup_logging, runbrick, SimCatalog, RunCatalog, get_sim_id, find_file, utils
from legacysim.analysis import ImageAnalysis
from legacysim.scripts import check, merge, match, resources, cutout
from test_runbrick import generate_injected


setup_logging()


survey_dir = os.path.join(os.path.dirname(__file__), 'testcase3')
output_dir = 'out-testcase3-legacysim'
legacypipe_dir = 'out-testcase3-legacypipe'
injected_fn = os.path.join(output_dir,'input_injected.fits')
brickname = '2447p120'
zoom = [1020,1070,2775,2815]


def test_runbrick():

    os.environ['GAIA_CAT_DIR'] = os.path.join(survey_dir, 'gaia')
    os.environ['GAIA_CAT_VER'] = '2'

    lprunbrick.main(args=['--brick', brickname, '--zoom', *map(str,zoom),
                        '--no-wise', '--force-all', '--no-write',
                        '--survey-dir', survey_dir,
                        '--outdir', legacypipe_dir,
                        '--threads', '1'])

    injected = generate_injected(brickname,zoom=zoom,mag_range=[19.,20.],shape_r_range=[0.,0.],size=5)
    injected.writeto(injected_fn)

    runbrick.main(args=['--brick', brickname, '--zoom', *map(str,zoom),
                        '--no-wise', '--force-all',
                        '--survey-dir', survey_dir,
                        '--injected-fn', injected_fn,
                        '--outdir', output_dir,
                        '--seed', 42,
                        '--ps',
                        '--threads', 1])


def test_check():

    base_kwargs = {'outdir':output_dir,'brick':brickname}

    bricklist_fn = os.path.join(base_kwargs['outdir'],'bricklist.txt')
    with open(bricklist_fn,'w') as file:
        file.write(brickname+'\n')

    for extra_kwargs in [{},
                        {'outdir':legacypipe_dir,'source':'legacypipe'},
                        {'read':''},
                        {'stages':['fitblobs','writecat'],'read':''},
                        {'brick':'2447p121'},
                        {'brick':bricklist_fn},
                        {'fileid':3},
                        {'rowstart':3},
                        {'skipid':5,'write':''},
                        {'fileid':3,'write':os.path.join(output_dir,'runlist.txt')}]:

        all_kwargs = {**base_kwargs,**extra_kwargs}
        runcat = check.main(all_kwargs)

        if (all_kwargs['brick'] in [brickname,bricklist_fn]) and (get_sim_id.as_dict(**all_kwargs) == get_sim_id.as_dict()):
            assert runcat.size == 0
            continue
        assert runcat.size == 1
        assert np.all(runcat.brickname == all_kwargs['brick'])
        for key,val in get_sim_id.as_dict(**all_kwargs).items():
            assert np.all(runcat.get(key) == val)
        if 'write' in all_kwargs:
            fn = extra_kwargs['write']
            if not fn: fn = 'runlist.txt'
            runlist = RunCatalog.from_list(fn)
            assert runlist == runcat
            os.remove(fn)


def test_merge():

    base_kwargs = {'outdir':output_dir,'cat-dir':os.path.join(output_dir,'merged'),'fileid':0,'skipid':0,'rowstart':0}
    for extra_kwargs in [{'outdir':legacypipe_dir,'source':'legacypipe','filetype':'tractor'},
                        {'source':'legacysim','filetype':'tractor'},
                        {'filetype':'injected','cat-fn':os.path.join(base_kwargs['cat-dir'],'merged_injected.fits')},
                        ]:
        all_kwargs = {**base_kwargs,**extra_kwargs}
        merge.main(all_kwargs)
        source = all_kwargs.get('source','legacysim')
        filetype = all_kwargs['filetype']
        if 'cat-fn' in all_kwargs:
            cat_fn = all_kwargs['cat-fn']
        elif source == 'legacypipe':
            cat_fn = os.path.join(all_kwargs['cat-dir'],'merged_%s_legacypipe.fits' % filetype)
        else:
            cat_fn = os.path.join(all_kwargs['cat-dir'],'merged_%s.fits' % filetype)
        merged = SimCatalog(cat_fn)
        origin = SimCatalog(find_file(base_dir=all_kwargs['outdir'],filetype=filetype,
                                        source=source,brickname=brickname,**get_sim_id.as_dict(**all_kwargs)))
        if filetype == 'injected':
            origin.cut(~origin.collided)
        assert merged.size == origin.size
        for field in origin.fields:
            assert np.all(merged.get(field) == origin.get(field))


def test_match():

    injected = SimCatalog(find_file(base_dir=output_dir,source='legacysim',filetype='injected',brickname=brickname))
    output = SimCatalog(find_file(base_dir=output_dir,source='legacysim',filetype='tractor',brickname=brickname))
    base_kwargs = {'outdir':output_dir,'cat-dir':os.path.join(output_dir,'merged'),'fileid':0,'skipid':0,'rowstart':0}
    for extra_kwargs in [{},
                        {'tractor':os.path.join(output_dir,'merged','merged_tractor.fits')},
                        {'tractor':os.path.join(output_dir,'merged','merged_tractor.fits'),
                        'injected':os.path.join(output_dir,'merged','merged_injected.fits')},
                        {'cat-fn':os.path.join(base_kwargs['cat-dir'],'test.fits')},
                        {'tractor':os.path.join(output_dir,'merged','merged_tractor.fits'),'tractor-legacypipe':legacypipe_dir},
                        {'tractor-legacypipe':os.path.join(output_dir,'merged','merged_tractor_legacypipe.fits')},
                        {'base':'inter','radius':5.},
                        {'base':'extra'},
                        {'base':'all'},
                        {'plot-hist':''},
                        {'plot-scatter':''}]:
        all_kwargs = {**base_kwargs,**extra_kwargs}
        match.main(all_kwargs)
        base = all_kwargs.get('base','input')
        fn = all_kwargs.get('cat-fn',os.path.join(base_kwargs['cat-dir'],'matched_%s.fits' % base))
        radius_in_degree = all_kwargs.get('radius',1.5)/3600.
        all_input = injected.copy()
        all_input.cut(~all_input.collided)
        tractor_legacypipe = all_kwargs.get('tractor-legacypipe',None)
        if tractor_legacypipe is not None:
            if not os.path.isfile(tractor_legacypipe):
                tractor_legacypipe = find_file(base_dir=tractor_legacypipe,filetype='tractor',source='legacypipe',brickname=brickname)
            tractor = SimCatalog(tractor_legacypipe)
            all_input.fill(tractor,index_self='after')
        inter_input,inter_output = all_input.match_radec(output,nearest=True,radius_in_degree=radius_in_degree,return_distance=False)
        matched = SimCatalog(fn)

        def nanall(tab1,tab2):
            if (tab1.size == 0) and (tab1.size == tab2.size):
                return True
            if isinstance(tab1.flat[0],np.floating):
                mask = ~np.isnan(tab1)
                return np.all(tab1[mask] == tab2[mask])
            return np.all(tab1 == tab2)

        if base == 'input':
            assert matched.size == all_input.size
            for field in all_input.fields:
                assert nanall(matched.get('input_%s' % field),all_input.get(field))
        if base == 'output':
            assert matched.size == output.size
            for field in output.fields:
                assert nanall(matched.get(field),output.get(field))
        if base == 'inter':
            assert matched.size == inter_input.size
            for field in all_input.fields:
                assert nanall(matched.get('input_%s' % field),all_input.get(field)[inter_input])
        if base == 'extra':
            assert matched.size == all_input.size + output.size - 2*inter_input.size
            extra_input = np.setdiff1d(all_input.index(),inter_input)
            extra_output = np.setdiff1d(output.index(),inter_output)
            for field in all_input.fields:
                assert nanall(matched.get('input_%s' % field)[:extra_input.size],all_input.get(field)[extra_input])
            for field in output.fields:
                assert nanall(matched.get(field)[extra_input.size:],output.get(field)[extra_output])
        if base == 'all':
            assert matched.size == all_input.size + output.size
            for field in all_input.fields:
                assert nanall(matched.get('input_%s' % field)[:all_input.size],all_input.get(field))
            for field in output.fields:
                assert nanall(matched.get(field)[all_input.size:],output.get(field))
        if 'plot-hist' in extra_kwargs:
            fn = all_kwargs['plot-hist']
            if not fn: fn = os.path.join(all_kwargs['cat-dir'],'hist_output_input.png')
            assert os.path.isfile(fn)
        if 'plot-scatter' in extra_kwargs:
            fn = all_kwargs['plot-scatter']
            if not fn: fn = os.path.join(all_kwargs['cat-dir'],'scatter_output_input.png')
            assert os.path.isfile(fn)


def test_resources():

    base_kwargs = {'outdir':output_dir,'fileid':0,'skipid':0,'rowstart':0}
    for extra_kwargs in [{},
                        {'do':'summary'},
                        {'do':'single','plot-fn':os.path.join(output_dir,'single_resources.png')}]:
        all_kwargs = {**base_kwargs,**extra_kwargs}
        resources.main(all_kwargs)
        do = all_kwargs.get('do','summary')
        fn = all_kwargs.get('plot-fn',None)
        if fn is None:
            if do == 'summary':
                fn = 'resources-summary.png'
            if do == 'single':
                fn = find_file(base_dir=output_dir,filetype='ps',brick=brickname)
                fn = fn[:-len('.fits')] + '.png'
        else:
            fn = fn % {**{'outdir':all_kwargs['outdir'],'brick':brickname},**get_sim_id.as_dict()}
        assert os.path.isfile(fn)
        os.remove(fn)


def test_cutout():

    image = ImageAnalysis(output_dir,brickname=brickname)
    filetypes = ['image-jpeg','model-jpeg','resid-jpeg']
    #image.read_image(filetype=filetypes[0],xmin=zoom[0],ymin=zoom[2])
    image.read_image(filetype=filetypes[0])
    image.read_image_wcs()
    image.read_sources(filetype='injected')
    slicex,slicey = image.suggest_zooms(boxsize_in_pixels=20,range_observed_injected_in_degree=[0.,1.])[0]
    #filetypes = ['image','model']
    fig,lax = plt.subplots(ncols=len(filetypes),sharex=False,sharey=False,figsize=(4*len(filetypes),4),squeeze=False)
    fig.subplots_adjust(hspace=0.2,wspace=0.2)
    lax = lax.flatten()

    for ax,filetype in zip(lax,filetypes):
        image.read_image(filetype=filetype)
        image.set_subimage(slicex,slicey)
        image.plot(ax)
        image.plot_sources(ax)
    utils.savefig(fn=os.path.join(output_dir,'injected_sources.png'))

    base_kwargs = {'outdir':output_dir}
    for extra_kwargs in [{},
                        {'ncuts':2,'plot-fn':os.path.join(output_dir,'cutout-%(brickname)s-%(icut)d.png')}]:
        all_kwargs = {**base_kwargs,**extra_kwargs}
        cutout.main(all_kwargs)
        fn = all_kwargs.get('plot-fn',None)
        if fn is None:
            image_fn = find_file(base_dir=output_dir,source='legacysim',filetype='image-jpeg',brickname=brickname)
            fn = os.path.join(os.path.dirname(image_fn),'cutout-%(brickname)s-%(icut)d.png')
        ncuts = all_kwargs.get('ncuts',np.inf)
        paths = glob.glob(fn.replace('%(icut)d.png','*.png')  % {'brickname':brickname})
        assert (len(paths) >= 1) and (len(paths) <= ncuts)
        for fn in paths: os.remove(fn)
