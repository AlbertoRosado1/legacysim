import os
import tempfile
import logging
import argparse

import numpy as np

from legacysim import setup_logging, BaseCatalog, SimCatalog, BrickCatalog, RunCatalog, get_sim_id, find_file, utils
from legacysim.catalog import Versions, Stages, ListStages


setup_logging(logging.DEBUG)


def test_base():

    cat = BaseCatalog()
    cat.ra = np.ones(10)
    assert cat.size == 10
    cat = BaseCatalog(size=100)
    cat.ra,cat.dec = cat.zeros(),cat.ones()
    assert 'ra' in cat
    assert cat.ra.size == 100
    assert np.all(cat.dec == cat.ra+1)
    assert cat.trues().all()
    assert not cat.falses().any()
    assert np.isnan(cat.nans()).all()
    assert np.all(cat.full(4) == 4)
    cat2 = cat.copy()
    cat2.ra[:] += 1
    assert np.all(cat.ra == 0)
    mask = cat.falses()
    mask[:50] = True
    cat2 = cat2[mask]
    assert len(cat2) == 50
    with tempfile.TemporaryDirectory() as tmp_dir:
        fn = os.path.join(tmp_dir,'tmp.fits')
        cat.writeto(fn)
        cat2 = BaseCatalog(fn)
    assert cat2 == cat
    cat2 = 0
    cat2 += cat + 0
    cat2 = cat2 + cat
    assert cat2.size == 200
    cat.flux = np.linspace(0.,1.,cat.size)
    cat.shape_r = np.linspace(0.,1.,cat.size).astype('f4')
    cat.type = np.full(cat.size,'DEV')
    cat2.fill(cat,index_self=100+np.arange(cat.size),index_other=np.arange(cat.size),fields_other=['ra','dec'])
    assert cat2.fields == ['ra','dec']
    cat2.fill(cat,index_self=100+np.arange(cat.size),index_other=np.arange(cat.size))
    assert ('flux' in cat2) and ('shape_r' in cat2)
    assert np.isnan(cat2.flux[:100]).all() and np.isnan(cat2.shape_r[:100]).all()
    cat3 = cat2[slice(0,0)]
    cat3.fill(cat,index_self='after',index_other=np.arange(cat.size),fields_other=['ra','dec'])
    assert cat3.size == cat.size
    assert np.isnan(cat3.flux).all() and np.isnan(cat3.shape_r).all()
    assert np.all(cat3.ra == cat.ra) and np.all(cat3.dec == cat.dec)
    cat4 = cat3.copy()
    cat3.fill(cat,index_self='after',index_other=np.arange(0),fields_other=['ra','dec'])
    assert cat3 == cat4
    cat3.fill(cat,index_self='before')
    assert np.all(cat3.flux[:cat.size] == cat.flux) and np.all(cat3.shape_r[:cat.size] == cat.shape_r)
    cat2.keep_columns('ra','dec')
    assert cat2.fields == ['ra','dec']
    cat2.delete_columns('ra','dec')
    assert cat2.fields == []
    cat2.ra,cat2.dec,cat2.id = cat2.zeros(),cat2.ones(),cat2.full('id')
    assert np.all(cat2.to_recarray('ra').ra == cat2.ra)
    array = cat2.to_ndarray()
    assert np.all(array['ra'] == cat2.ra) and np.all(array['dec'] == cat2.dec)
    cat2.dec[0] = 0
    cat2.id[0] = 'aa'
    unique,index = cat2.unique('ra',return_index=True)
    assert np.all(unique.ra == 0.) and np.all(index == 0)
    unique,index = cat2.unique(return_index=True)
    assert np.all(unique == cat2[:2]) and np.all(index == [0,1])
    cat2.ra[1] = 1
    unique,index,inverse = cat2.unique(return_index=True,sort_index=True,return_inverse=True)
    assert np.all(unique == cat2[:3]) and np.all(index == [0,1,2])
    for sort_index in [False,True]:
        assert cat2.unique(sort_index=sort_index,return_unique=False) == ()
        assert isinstance(cat2.unique(sort_index=sort_index),BaseCatalog)
        unique,index = cat2.unique(sort_index=sort_index,return_index=True)
        assert unique == cat2[index]
        unique,index,inverse = cat2.unique(sort_index=sort_index,return_index=True,return_inverse=True)
        assert unique[inverse] == cat2
        unique,index,inverse,counts = cat2.unique(sort_index=sort_index,return_index=True,return_inverse=True,return_counts=True)
        assert counts.sum() == cat2.size
    assert np.all(unique[inverse] == cat2)
    cat3 = cat2.remove_duplicates(copy=True)
    assert cat3.size == 3
    assert cat3 == cat2[:cat3.size]
    cat4 = cat2.copy()
    cat4.remove_duplicates()
    assert cat4 == cat3
    cat3 = cat2.remove_duplicates(fields='id',copy=True)
    assert cat3.size == 2
    assert cat3 == cat2[:cat3.size]
    uniqid = cat2.uniqid(fields='id')
    assert np.all(uniqid == cat2.id)
    uniqid = cat2.uniqid()
    assert (uniqid.ndim == 1) and (uniqid.size == cat2.size)
    assert np.unique(uniqid).size == cat4.size
    assert cat2.isin(cat4).all()
    assert np.all(np.flatnonzero(cat2.isin(cat3)) == [0,1])
    assert cat2.isin(cat3,fields='id').all()
    cat3 = cat4.tile(4,copy=True)
    assert np.all(cat3.ra == np.concatenate([cat4.ra]*4))
    cat3.tile(2,copy=False)
    assert np.all(cat3.id == np.concatenate([cat4.id]*8))
    cat3.remove_duplicates()
    assert cat3 == cat4
    cat3 = cat4.repeat(3,copy=True)
    #print(cat3.ra,cat4.ra,cat3.size,cat4.size)
    assert np.all(cat3.ra[::3] == cat4.ra) and np.all(cat3.ra[1::3] == cat4.ra) and np.all(cat3.ra[2::3] == cat4.ra)
    cat2 = cat4.copy()
    cat4.repeat(6,copy=False)
    assert np.all(cat3.id == cat4.id[::2]) and np.all(cat3.id == cat4.id[1::2])
    assert cat4.remove_duplicates() == cat2


def test_sim():

    cat = SimCatalog(size=100)
    cat.ra, cat.dec = utils.sample_ra_dec(size=cat.size,radecbox=[259.9,260.1,18.7,18.8],seed=20)
    cat.fill_legacysim()
    assert np.all(cat.id == np.arange(len(cat)))
    assert np.all(cat.brickname == '2599p187')
    assert 'seed' in cat.fields
    seed = cat.seed.copy()
    cat.fill_legacysim()
    assert np.all(cat.seed == seed)
    cat.fill_legacysim(seed=42)
    assert not np.all(cat.seed == seed)
    mask = cat.mask_collisions(radius_in_degree=1.)
    assert mask[1:].all()
    ind1,ind2 = cat.match_radec(cat[::-1],radius_in_degree=1e-6)
    assert (ind1 == ind2[::-1]).all()


def test_brick():

    bricks = BrickCatalog()
    brick = bricks.get_by_name(['2599p187'])
    assert len(brick.get('brickid')) == 1
    brick = bricks.get_by_name('2599p187')
    assert np.isscalar(brick.get('brickid'))
    brick = bricks.get_by_radec([259.91]*2,[18.71]*2)
    assert len(brick) == 2 and np.all(brick.brickname == '2599p187')
    brick2 = bricks[bricks.ra1>240].get_by_radec([259.91]*2,[18.71]*2)
    assert len(brick2) == 2 and np.all(brick2.brickname == '2599p187')
    radecbox = brick.get_radecbox(total=False)
    radecbox = brick.get_radecbox(total=True)
    assert np.all([np.isscalar(x) for x in radecbox])
    radecbox = bricks.get_radecbox(total=True)
    assert np.allclose(radecbox,(0.,360.,-90.,90.))
    area = brick.get_area(total=True)
    assert np.isscalar(area)
    area = bricks.get_area(total=True)
    assert np.allclose(area,4.*np.pi*(180./np.pi)**2)
    x,y = bricks.get_xy_from_radec(259.91,18.71)
    assert np.isscalar(x) and np.isscalar(y)
    x,y = bricks.get_xy_from_radec([259.91]*2,[18.71]*2,brickname=['2599p187']*2)
    assert (x>=0).all() and (x<=3600).all() and (y>=0).all() and (y<=3600).all()
    x2,y2 = brick.get_xy_from_radec([259.91]*2,[18.71]*2)
    assert np.allclose(x2,x) and np.allclose(y2,y)
    x3,y3 = bricks.get_xy_from_radec([13.42]+[259.91]*2+[97.81],[21.12]+[18.71]*2+[48.51])
    assert np.allclose(x3[1:-1],x) and np.allclose(y3[1:-1],y)
    with tempfile.TemporaryDirectory() as tmp_dir:
        fn = os.path.join(tmp_dir,'bricklist.txt')
        bricks.get_by_name(['2599p187']*2).write_list(fn)
        with open(fn,'r') as file:
            bricknames = []
            for line in file:
                bricknames.append(line.replace('\n',''))
            assert bricknames == ['2599p187']*2
        bricknames = BrickCatalog.read_list(['2599p187',fn])
        assert bricknames == ['2599p187']
        bricknames = BrickCatalog.read_list(['2599p187',fn],unique=False)
        assert bricknames == ['2599p187']*3


def test_stages():

    v = Versions()
    assert v.data == {}
    v1 = Versions({'a':'v1','b':'v1:2'})
    assert Versions(**{'a':'v1','b':'v1:2'}) == v1
    assert Versions('a:v1,b:v1:2') == v1
    v2 = Versions(['b:v1:2',('a','v1')])
    assert v2 == v1
    assert list(v2.keys()) == ['a','b']
    assert str(v2) == 'a:v1,b:v1:2'
    s = Stages()
    assert s.data == {'writecat':Versions()}
    s1 = Stages({'fitblobs':{'c':'v3'},'outliers':v1})
    assert Stages('fitblobs:c:v3 outliers:a:v1,b:v1:2') == s1
    s2 = Stages([('fitblobs','c:v3'),'outliers:a:v1,b:v1:2'])
    assert s2 == s1
    assert list(s2.keys()) == ['outliers','fitblobs']
    assert str(s2) == 'outliers:a:v1,b:v1:2 fitblobs:c:v3'
    assert all(s2.isin(s2))
    assert np.all(s2.isin(Stages('outliers:a:v1,b:v1:2 tims')) == [True,False])
    s3 = s2.without_versions()
    assert str(s3) == 'fitblobs'
    assert not any(s2.isin(s3))
    l1 = ListStages()
    assert l1.append(s) == 0
    assert l1.append(s1) == 1
    assert l1.append(s3) == 2
    assert s1 in l1
    assert l1.index(s1) == 1
    assert Versions('writecat:a:v4') not in l1
    assert l1.index('halos:a:v4') == -1
    l2 = ListStages([s,{'fitblobs':{'c':'v3'},'outliers':v1}])
    l3,i3 = l1.without_versions()
    assert l3 == l2.without_versions()[0]
    assert i3 == [0,1,1]
    l2 = ListStages([s1,s])
    i1,i2 = l2.match(l3)
    assert i1 == [1,-1] and i2 == [-1,0]


def test_run():

    parser = RunCatalog.get_input_parser(add_stages=False)
    assert utils.list_parser_dest(parser) == get_sim_id.keys() + ['brick','list']
    parser = argparse.ArgumentParser()
    RunCatalog.get_input_parser(parser=parser,add_stages=True)
    assert utils.list_parser_dest(parser) == get_sim_id.keys() + ['brick','list','stages']
    parser = RunCatalog.get_output_parser(parser=None,add_stages=True)
    assert utils.list_parser_dest(parser) == ['output_dir'] + get_sim_id.keys() + ['brick','list','stages','pickle_pat']
    parser = argparse.ArgumentParser()
    parser = RunCatalog.get_output_parser(parser,add_stages=True,add_filetype=True,add_source=True)
    assert utils.list_parser_dest(parser) == ['output_dir'] + get_sim_id.keys() + ['brick','list','stages','pickle_pat','filetype','source']

    class opt:
        pass

    RunCatalog.set_default_output_cmdline(opt)
    keys_defs = ['source','stages','pickle_pat','filetype']
    for key in keys_defs:
        assert hasattr(opt,key)
    opt = {}
    RunCatalog.set_default_output_cmdline(opt)
    for key in keys_defs:
        assert key in opt
    opt = dict(zip(get_sim_id.keys(),[[0,1],[0,500],[0,0]]))
    nsimid = len(list(opt.values())[0])
    kwargs_simids = RunCatalog.kwargs_simids_from_cmdline(opt)
    assert kwargs_simids == [{key:opt[key][i] for key in get_sim_id.keys()} for i in range(nsimid)]
    bricknames = ['2599p187','2599p188','2599p189']
    with tempfile.TemporaryDirectory() as tmp_dir:
        fn = os.path.join(tmp_dir,'bricklist.txt')
        with open(fn,'w') as file:
            for brick in bricknames:
                file.write(brick + '\n')
        fn2 = os.path.join(tmp_dir,'bricklist2.txt')
        with open(fn2,'w') as file:
            for brick in bricknames[1:]:
                file.write(brick + '\n')
        opt['brick'] = [bricknames[1],fn,fn2]
        runcat = RunCatalog.from_input_cmdline(opt)
        assert set(runcat.brickname) == set(bricknames)
        assert len(runcat) == len(bricknames) * nsimid
        assert np.all(runcat.stagesid == 0)
        assert len(runcat.get_list_stages()) == 1
        assert runcat.get_list_stages()[0] == Stages('writecat')
        runcat1 = runcat.copy()
        runcat1.replace_sim_id()
        for key,d in zip(get_sim_id.keys(),get_sim_id.default()):
            assert np.all(runcat1.get(key) == d)
        runcat2 = runcat1.replace_sim_id(copy=True,kwargs_simids=kwargs_simids)
        assert runcat2 == runcat
        runcat2 = runcat1.tile(2,copy=True)
        runcat2.fileid[runcat1.size:] = 100 # import to set new runcat.fileid otherwise not licit
        runcat2.stagesid[runcat1.size:] = istages = runcat2.append_stages('outliers:a:v1 writecat')
        assert (istages == 1) and (len(runcat2.get_list_stages()) == 2)
        runcat3 = RunCatalog.from_catalog(runcat2,stages='writecat')
        assert runcat3.get_list_stages() == ListStages([Stages()])
        runcat4 = RunCatalog.from_catalog(runcat3,stages='fitblobs')
        assert runcat4.get_list_stages() == ListStages([Stages('fitblobs')])
        runcat3 = RunCatalog.from_catalog(runcat2,list_stages=runcat2.get_list_stages())
        assert runcat3 == runcat2
        runcat3.stagesid[runcat1.size:] = istages = runcat3.append_stages('outliers:a:v1 writecat:a:v2')
        assert (istages == 2) and (len(runcat3.get_list_stages()) == 3)
        assert runcat3.isin(runcat2,ignore_stage_version=True).all()
        mask = runcat3.isin(runcat2)
        assert mask[:runcat1.size].all() and not mask[runcat1.size].any()
        runcat3.stagesid[runcat1.size:] = istages = runcat2.append_stages('outliers:a:v1 writecat')
        assert (istages == 1) and (len(runcat3.get_list_stages()) == 3)
        fn3 = os.path.join(tmp_dir,'run_list.fits')
        runcat2.writeto(fn3)
        fn4 = os.path.join(tmp_dir,'run_list.txt')
        runcat2.write_list(fn4)
        runcat3 = RunCatalog(fn3)
        runcat4 = RunCatalog.from_list(fn4)
        assert runcat3 == runcat2
        assert runcat4 == runcat2
        assert runcat3.get_list_stages() == runcat4.get_list_stages()
        assert len(runcat3.get_list_stages()) == 2
        assert runcat3.count_runs(runcat3) == runcat3.size
        cat = BaseCatalog(runcat3.to_ndarray())
        cat.keep_columns('brickname')
        assert runcat3.count_runs(cat) == runcat1.size
        runcat4 = runcat1.copy()
        runcat4.append(runcat3)
        assert runcat4 == runcat3
        runcat3.stagesid[:runcat1.size] = runcat3.append_stages('outliers:a:v1 writecat:b:v2')
        runcat3.append(runcat4)
        assert runcat3.size == 3*runcat1.size
        ok = False
        try:
            runcat3.check()
        except ValueError:
            ok = True
        assert ok
        runcat3.fileid[:runcat1.size] = 200
        runcat3.check()
        assert len(runcat3.get_list_stages()) == 3
        assert RunCatalog.from_output_cmdline(opt) == runcat
        assert RunCatalog.from_output_cmdline({'list':fn4}) == runcat2
        runcat.write_list(fn4)
        template_pickle = os.path.join(tmp_dir,'pickles/runbrick-%(brick)s-%(simid)s-%%(stage)s.pickle')
        for brickname in bricknames:
            for kwargs_simid in kwargs_simids:
                fntmp = find_file(base_dir=tmp_dir,brickname=brickname,source='legacypipe',filetype='tractor',**kwargs_simid)
                SimCatalog().writeto(fntmp)
                fntmp = find_file(base_dir=tmp_dir,brickname=brickname,source='legacysim',filetype='injected',**kwargs_simid)
                SimCatalog().writeto(fntmp)
                for stage in ['outliers','fitblobs']:
                    fntmp = find_file(base_dir=tmp_dir,brickname=brickname,source='legacysim',filetype='pickle',stage=stage,**kwargs_simid)
                    utils.mkdir(os.path.dirname(fntmp))
                    with open(fntmp,'w') as file:
                        file.write('ok')
                fntmp = template_pickle % {'brick':brickname,'simid':get_sim_id(**kwargs_simid)} % {'stage':'fitblobs'}
                utils.mkdir(os.path.dirname(fntmp))
                with open(fntmp,'w') as file:
                    file.write('ok')
        runcat2 = RunCatalog.from_output_cmdline({'list':fn4,'output_dir':tmp_dir},force_from_disk=True)
        assert runcat2.to_ndarray().sort() == runcat.to_ndarray().sort()
        for tmpopt in [{'output_dir':tmp_dir,'source':'legacypipe'},
                        {'output_dir':tmp_dir,'brick':bricknames,'source':'legacypipe'},
                        {'output_dir':tmp_dir,'filetype':'injected'},
                        {'output_dir':tmp_dir,'stages':'outliers'},
                        {'output_dir':tmp_dir,'stages':'outliers fitblobs','brick':bricknames},
                        {'output_dir':tmp_dir,'stages':'fitblobs','pickle_pat':template_pickle},
                        {'output_dir':tmp_dir,'stages':'fitblobs','pickle_pat':template_pickle,'brick':bricknames}]:
            runcat2 = RunCatalog.from_output_cmdline(tmpopt)
            assert set(runcat2.brickname) == set(bricknames)
            tmp_kwargs_simids = []
            for run in runcat2:
                if run.kwargs_simid not in tmp_kwargs_simids:
                    tmp_kwargs_simids.append(run.kwargs_simid)
            assert set(map(frozenset,tmp_kwargs_simids)) == set(map(frozenset,kwargs_simids))
