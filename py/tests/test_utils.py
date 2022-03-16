import os
import tempfile
import logging
import argparse

import numpy as np

from legacysim import setup_logging
from legacysim.utils import (saveplot, MonkeyPatching, get_parser_args, list_parser_dest, get_parser_action_by_dest,
                            match_id, sample_ra_dec, match_radec, mask_collisions, get_radecbox_area,
                            get_shape_e1_e2, get_shape_ba_phi, mag2nano, nano2mag, get_extinction)


setup_logging(logging.DEBUG)


def test_plots():
    with tempfile.TemporaryDirectory() as tmp_dir:

        @saveplot()
        def plot(self, ax,label='label'):
            ax.plot(np.linspace(0.,1.,10))

        fn = os.path.join(tmp_dir,'plot.png')
        plot(0,fn=fn)
        assert os.path.isfile(fn)


def test_monkey_patching():
    import legacysim

    def test():
        return True

    def test2():
        return 'file'

    with MonkeyPatching() as mp:
        mp.add(legacysim,'test',test)
        mp.add(legacysim,'find_file',test2)
        mp.add(np,'sillyname',test2)
        assert legacysim.test()
        assert legacysim.find_file() == 'file'
        assert np.sillyname()
        assert hasattr(np,'sillyname')
        assert (legacysim,'find_file') in mp
        assert list(mp.keys()) == [(legacysim,'test'),(legacysim,'find_file'),(np,'sillyname')]
        mp.remove(legacysim,'test')
        assert list(mp.keys()) == [(legacysim,'find_file'),(np,'sillyname')]
        assert not hasattr(legacysim,'test')
        mp.clear()
        assert list(mp.keys()) == []
        assert hasattr(legacysim,'find_file')
        assert not hasattr(np,'sillyname')
        mp.add(legacysim,'find_file',test)
        mp.add(legacysim,'find_file2',test2)
        assert legacysim.find_file()
    assert not hasattr(legacysim,'find_file2')


def test_misc():

    parent = argparse.ArgumentParser(add_help=True)
    parent.add_argument('--apodize', default=False, action='store_true',
    					help='Apodize image edges for prettier pictures?')
    parser = argparse.ArgumentParser(add_help=False,parents=[parent])
    parser.add_argument('-r', '--run', default=None,
    					help='Set the run type to execute')
    group = parser.add_argument_group('legacysim', 'legacysim-specific arguments')
    group.add_argument(
    	'-f', '--force-stage', dest='force', action='append', default=[],
    	help="Force re-running the given stage(s) -- don't read from pickle.")
    group.add_argument('--sim-blobs', action='store_true',
    					help='Process only the blobs that contain simulated sources.')
    dests = ['apodize','run','force','sim_blobs']
    assert list_parser_dest(group) == dests
    for dest in dests:
        assert get_parser_action_by_dest(parser,dest).dest == dest
    """
    # Works but file not created in pytest...
    with tempfile.TemporaryDirectory() as tmp_dir:
        fn = os.path.join(tmp_dir,'log.out')
        setup_logging(logging.INFO,filename=fn)
        words = 'TESTlegacysim'
        logger.info(words)
        ok = False
        with open(fn,'r') as tmp:
            for line in tmp.readlines():
                if words in line:
                    ok = True
                    break
        assert ok
    """
    truth = ['--a','1','--b','2']
    args = '--a 1 --b 2'
    assert get_parser_args(args) == truth
    args = ['--a',1,'--b',2]
    assert get_parser_args(args) == truth
    args = {'a':1,'b':2}
    assert get_parser_args(args) == truth

    id1 = np.arange(4)
    id2 = np.array([1,3,2,4,6])
    ind1,ind2 = match_id(id1,id2)
    assert len(ind1) == len(ind2) and len(ind1) == 3
    assert (id1[ind1] == id2[ind2]).all()


def test_radec():
    ramin,ramax,decmin,decmax = 259.9,260.2,18.7,18.8
    ra, dec = sample_ra_dec(size=None,radecbox=[ramin,ramax,decmin,decmax],seed=20)
    assert np.ndim(ra) == np.ndim(dec) == 0
    ra, dec = sample_ra_dec(size=20,radecbox=[ramin,ramax,decmin,decmax],seed=20)
    assert len(ra) == 20 and len(dec) == 20
    assert np.all((ra>=ramin) & (ra<=ramax) & (dec>=decmin) & (dec<=decmax))
    ind1,ind2 = match_radec(ra,dec,ra[::-1],dec[::-1])
    assert (ind1 == ind2[::-1]).all()
    mask = mask_collisions(ra,dec,radius_in_degree=1.)
    assert mask[1:].all()
    ra[:] = dec[:] = 0
    ra = np.linspace(0.,20.,ra.size)
    ra[:10] = 0.1
    mask = mask_collisions(ra,dec,radius_in_degree=0.5)
    assert mask[1:10].all() and not mask[10:].any()
    area = get_radecbox_area(ramin,ramax,decmin,decmax)
    assert np.ndim(area) == 0
    decfrac = np.diff(np.rad2deg(np.sin(np.deg2rad([decmin, decmax]))),axis=0)
    rafrac = np.diff([ramin, ramax],axis=0)
    assert np.allclose(area, decfrac*rafrac)
    ramin, ramax, decmin, decmax = [np.ones(4, dtype='f8')]*4
    assert get_radecbox_area(ramin,ramax,decmin,decmax).shape == (4, )


def test_quantities():
    ba,phi = 0.42,0.69
    e1,e2 = get_shape_e1_e2(ba,phi)
    ba_,phi_ = get_shape_ba_phi(e1,e2)
    assert np.allclose(ba,ba_) and np.allclose(phi,phi_)
    mag = 24.
    nano = mag2nano(mag)
    mag2 = nano2mag(nano)
    assert np.allclose(mag, mag2)
    ra,dec = 12,4
    ebvref = get_extinction(ra,dec)
    assert np.ndim(ebvref) == 0 and np.allclose(ebvref, 0.01896500348082133)
    ebv = get_extinction([ra]*4,[dec]*4)
    assert (ebv.size==4) and np.allclose(ebv,ebvref)
    trans_g = get_extinction(ra,dec,band='g',camera='DES')
    assert (ebv.size==4) and np.allclose(trans_g,3.214*ebv)


if __name__ == '__main__':

    test_plots()
    test_monkey_patching()
    test_misc()
    test_radec()
    test_quantities()
