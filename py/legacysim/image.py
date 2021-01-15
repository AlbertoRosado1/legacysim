"""Classes to extend :mod:`legacypipe.image`."""

import os
import re
import logging

import numpy as np
from legacypipe.decam import DecamImage
from legacypipe.bok import BokImage
from legacypipe.mosaic import MosaicImage
from legacypipe.ptf import PtfImage
from legacypipe.cfht import MegaPrimeImage
from legacypipe.runcosmos import DecamImagePlusNoise
from astrometry.util.ttime import Time
import tractor
import galsim


logger = logging.getLogger('legacysim.image')


class GSImage(galsim.Image):
    """Extend :class:`galsim.Image`, with other ``__setitem__`` options."""

    def __setitem__(self, *args):
        """
        Extend ``galsim.Image.__setitem__`` to allow:
            - numpy-style ``self[ndarray1] = ndarray2``
            - hybdrid-style ``self[bounds] = ndarray``
        """
        if len(args) == 2:
            # allows numpy-style ``self[ndarray1] = ndarray2``
            if isinstance(args[0], np.ndarray):
                self._array[args[0]] = args[1]
                return
            # allows settings ``self[bounds] = ndarray``
            if isinstance(args[0], galsim.BoundsI) and isinstance(args[1], np.ndarray):
                args = (args[0],self.__class__(args[1], bounds=args[0]))
        super(GSImage,self).__setitem__(*args)


def _Image(array, bounds, wcs):
    """
    Function of :mod:`galsim.image` redefined to have all methods of :class:`galsim.Image` consistent within :class:`GSImage` (e.g. :meth:`galsim.Image.copy`).

    Equivalent to ``GSImage(array, bounds, wcs)``, but without the overhead of sanity checks,
    and the other options for how to provide the arguments.
    """
    ret = GSImage.__new__(GSImage)
    ret.wcs = wcs
    ret._dtype = array.dtype.type
    if ret._dtype in GSImage._alias_dtypes:
        ret._dtype = GSImage._alias_dtypes[ret._dtype]
        array = array.astype(ret._dtype)
    ret._array = array
    ret._bounds = bounds
    return ret


galsim.image._Image = _Image


class BaseSimImage(object):
    """Dumb class that extends :meth:`legacypipe.image.get_tractor_image` for future multiple inheritance."""

    def get_tractor_image(self, **kwargs):

        get_dq = kwargs.get('dq', True)
        kwargs['dq'] = True # dq required in the following
        if not kwargs.get('nanomaggies', True):
            raise NotImplementedError('In legacysim, images are assumed to be in nanomaggies.')
        #print('slice',kwargs['slc'])
        tim = super(BaseSimImage,self).get_tractor_image(**kwargs)

        if tim is None: # this can be None when the edge of a CCD overlaps
            return tim

        tim_dq = GSImage(tim.dq,xmin=1,ymin=1)
        if not get_dq: del tim.dq

        if self.survey.injected is None or not len(self.survey.injected): # empty catalog
            return tim

        # Grab the data and inverse variance images [nanomaggies!]
        tim_image = GSImage(tim.getImage(),xmin=1,ymin=1)
        with np.errstate(divide='ignore', invalid='ignore'):
            tim_var = GSImage(1./tim.getInvvar(),xmin=1,ymin=1)
        # Also store galaxy sims and sims invvar
        sims_image = tim_image.copy()
        sims_image.fill(0.)
        sims_var = sims_image.copy()

        # Store simulated galaxy images in tim object
        # Loop on each object.
        if self.survey.sim_stamp == 'tractor':
            objstamp = TractorSimStamp(tim)
        else:
            objstamp = GalSimStamp(tim)

        any_overlap = False
        for obj in self.survey.injected:
            t0 = Time()
            logger.info('%s drawing object id=%d, band=%s, seed=%d: flux=%.2g, sersic=%.2f, shape_r=%.2f, shape_e1=%.2f, shape_e2=%.2f',
                objstamp.__class__.__name__,obj.id,objstamp.band,obj.seed,obj.get('flux_%s' % objstamp.band),obj.sersic,obj.shape_r,obj.shape_e1,obj.shape_e2)
            stamp = objstamp.draw(obj)
            if stamp is None:
                logger.debug('Stamp does not overlap tim for object id=%d',obj.id)
                continue
            t0 = logger.debug('Finished drawing object id=%d: band=%s flux=%.2f addedflux=%.2f in %s',
                obj.id,objstamp.band,obj.get('flux_%s' % objstamp.band),stamp.array.sum(),Time()-t0)
            overlap = stamp.bounds & tim_image.bounds
            # Add source if at least 1 pix falls on the CCD
            if overlap.area() > 0:
                any_overlap = True
                logger.debug('Stamp overlaps tim: id=%d band=%s',obj.id,objstamp.band)

                stamp = stamp[overlap].array
                nano2e = self.get_nano2e(tim=tim,x=np.arange(overlap.xmin,overlap.xmax+1),y=np.arange(overlap.ymin,overlap.ymax+1))

                if self.survey.add_sim_noise:
                    rng = np.random.RandomState(seed=obj.seed)
                    stamp_pos = stamp.clip(0)
                    if self.survey.add_sim_noise == 'gaussian':
                        logger.debug('Adding Gaussian noise.')
                        stamp += np.sqrt(stamp_pos)/np.sqrt(nano2e)*rng.randn(*stamp.shape)
                    else: # poisson
                        logger.debug('Adding Poisson noise.')
                        stamp += rng.poisson(stamp_pos*nano2e,size=stamp.shape)/nano2e - stamp_pos
                # Add stamp to image
                tim_image[overlap] += stamp
                # Compute stamp variance
                stamp_var = np.abs(stamp)/nano2e
                stamp_var[tim_dq[overlap].array > 0] = 0.
                tim_var[overlap] += stamp_var
                # Extra
                sims_image[overlap] += stamp
                sims_var[overlap] += stamp_var

        tim.sims_image = sims_image.array
        tim.sims_inverr = np.zeros_like(tim.sims_image)
        tim.sims_inverr[sims_var.array>0] = np.sqrt(1./sims_var.array[sims_var.array>0])
        if self.survey.image_eq_model:
            tim.data = tim.sims_image
            tim.inverr = tim.sims_inverr
        elif any_overlap: # no need to update if there was no overlap
            tim.data = tim_image.array
            tim.setInvvar(1./tim_var.array)

        return tim

    def get_zpscale(self):
        """Return zpscale for image units to nanomaggies conversion."""
        return tractor.NanoMaggies.zeropointToScale(self.ccdzpt)


class DecamSimImage(BaseSimImage,DecamImage):
    """
    Extend :class:`BaseSimImage` with :class:`legacypipe.decam.DecamImage`.

    Note
    ----
    Image unit is ADU (x gain -> electrons).

    References
    ----------
    http://ast.noao.edu/sites/default/files/NOAO_DHB_v2.2.pdf
    """

    def get_gain(self, tim, x, y):
        """
        Return gain at the one-indexed pixel position ``x``, ``y`` in the ``tim`` subimage.

        Parameters
        ----------
        tim : tractor.Image
            Current :class:`tractor.Image`.

        x : int, array-like
            Pixel one-indexed x-position in the ``tim`` subimage, 1-dim.

        y : int, array-like
            Pixel one-indexed y-position in the ``tim`` subimage, 1-dim.

        Returns
        -------
        gain : float, array-like
            Gain (ADU x gain -> electrons).
        """
        #print(self.width,self.height,self.survey.add_sim_noise,tim.x0,tim.y0,tim.hdr['GAINA'],tim.hdr['GAINB'])
        isscalarx,isscalary = np.isscalar(x),np.isscalar(y)

        def return_gain(g):
            if isscalarx: g = g[...,0]
            return g

        sipx = np.atleast_1d(tim.x0+x)
        assert sipx.ndim == 1
        gain = np.full(len(sipx) if isscalary else (len(y),len(sipx)),tim.hdr['GAINA'])
        halfw = self.width//2
        if halfw != 1023:
            logger.warning('Found halfw = %d for %s (expected 1023), defaults to average(GAINA,GAINB).',halfw,self.camera)
            gain[...] = np.average([tim.hdr['GAINA'],tim.hdr['GAINB']])
            return return_gain(gain)
        if self.ccdname.startswith('N'):
            maskb = sipx > halfw
        elif self.ccdname.startswith('S'):
            maskb = sipx <= halfw #sigpx 1-indexed
        else:
            raise ValueError('ccdname is expected to end with N or S')
        gain[...,maskb] = tim.hdr['GAINB']
        return return_gain(gain)

    def get_nano2e(self, *args, **kwargs):
        """Return nanomaggies to electron counts conversion."""
        return self.get_zpscale()*self.get_gain(*args,**kwargs)


class BokSimImage(BaseSimImage,BokImage):
    """
    Extend :class:`BaseSimImage` with :class:`legacypipe.bok.BokImage`.

    Note
    ----
    Image unit is electrons/second (x exptime -> electrons).
    """

    def get_nano2e(self, *args, **kwargs):
        """Return nanomaggies to electron counts conversion."""
        return self.get_zpscale()*self.exptime


class MosaicSimImage(BaseSimImage,MosaicImage):
    """
    Extend :class:`BaseSimImage` with :class:`legacypipe.mosaic.MosaicImage`.

    Note
    ----
    Image unit is electrons/second (x exptime -> electrons).
    """

    def get_nano2e(self, *args, **kwargs):
        """Return nanomaggies to electron counts conversion."""
        return self.get_zpscale()*self.exptime


class DecamSimImagePlusNoise(BaseSimImage,DecamImagePlusNoise):
    """
    Extend :class:`BaseSimImage` with :class:`DecamImagePlusNoise`.

    Note
    -----
    Image unit is ADU (x gain -> electrons).

    Warning
    -------
    Conversion should be checked further!
    """

    def get_gain(self, *args, **kwargs):
        """Return gain."""
        raise NotImplementedError

    def get_nano2e(self, *args, **kwargs):
        """Return nanomaggies to electron counts conversion."""
        raise NotImplementedError


class PtfSimImage(BaseSimImage,PtfImage):
    """
    Extend :class:`BaseSimImage` with :class:`legacypipe.ptf.PtfImage`.

    Note
    ----
    Image unit is ADU (x gain -> electrons).
    """

    def get_gain(self, tim, *args, **kwargs):
        """Return gain."""
        return tim.hdr['GAIN']

    def get_nano2e(self, *args, **kwargs):
        """Return nanomaggies to electron counts conversion."""
        return self.get_zpscale()*self.get_gain(*args,**kwargs)


class MegaPrimeSimImage(BaseSimImage,MegaPrimeImage):
    """
    Extend :class:`BaseSimImage` with :class:`legacypipe.cfht.MegaPrimeImage`.

    Note
    ----
    Image unit is ADU (x gain -> electrons).

    References
    ----------
    https://www.cfht.hawaii.edu/Instruments/Imaging/MegaPrime/rawdata.html#P2
    """

    def get_gain(self, tim, x, y):
        """
        Return gain at the one-indexed pixel position ``x``, ``y`` in the ``tim`` subimage.

        Parameters
        ----------
        tim : tractor.Image
            Current tractor.Image.

        x : int, array-like
            Pixel one-indexed x-position in the ``tim`` subimage, 1-dim.

        y : int, array-like
            Pixel one-indexed y-position in the ``tim`` subimage, 1-dim.

        Returns
        -------
        gain : float, array-like
            Gain (ADU x gain -> electrons).
        """
        #print(self.width,self.height,self.survey.add_sim_noise,tim.x0,tim.y0,tim.hdr['GAINA'],tim.hdr['GAINB'])
        isscalarx,isscalary = np.isscalar(x),np.isscalar(y)
        sipx = np.atleast_1d(tim.x0+x)
        assert sipx.ndim == 1
        gain = np.full(len(sipx) if isscalary else (len(y),len(sipx)),tim.hdr['GAINA'])
        limb = [int(s) for s in re.findall(r'\w+',tim.hdr['CSECB'])]
        maskb = (sipx >= limb[0]) & (sipx <= limb[1])
        gain[...,maskb] = tim.hdr['GAINB']
        if isscalarx:
            gain = gain[...,0]
        return gain

    def get_nano2e(self, *args, **kwargs):
        """Return nanomaggies to electron counts conversion."""
        return self.get_zpscale()*self.get_gain(*args, **kwargs)


class BaseSimStamp(object):
    """
    Draw model galaxies for a single image.

    Parent class to be inherited from to build different galaxy models.

    Attributes
    ----------
    tim : tractor.Image
        Tractor image.

    band : string
        Image band.

    xcen : float
        x center of the source in subimage pixel coordinates.

    ycen : float
        y center of the source in subimage pixel coordinates.

    attrs : dict
        Other attributes.
    """

    def __init__(self, tim, **attrs):
        """
        Parameters
        ----------
        tim : tractor.Image
            Current tractor.Image.

        attrs : dict
            Other attributes useful to define patches (e.g. ``nx``, ``ny``).
        """
        self.tim = tim
        self.band = tim.band
        self.attrs = attrs

    def set_local(self, ra, dec):
        """
        Set local :attr:`xcen`, :attr:`self.ycen` coordinates.

        Parameters
        ----------
        ra : float
            Right ascension (degree).

        dec : float
            Declination (degree).
        """
        # x,y coordinates one-indexed, as GSImage
        self.xcen, self.ycen = self.tim.subwcs.radec2pixelxy(ra,dec)[1:]


class TractorSimStamp(BaseSimStamp):
    """
    Extend :class:`BaseSimStamp` with generation of **Tractor** source stamps.

    Attributes
    ----------
    slcx : tuple
        x slice of the subimage where object will be generated.

    slcy : tuple
        y slice.
    """

    def get_subimage(self):
        """
        Return a subimage around :attr:`~BaseSimStamp.xcen`, :attr:`~BaseSimStamp.ycen`.

        Parameters
        ----------
        obj : SimCatalog row
            An object with attributes ``ra``, ``dec``.

        Returns
        -------
        tim : tractor.Image
            Subimage.
        """
        nx = self.attrs.get('nx',64)
        ny = self.attrs.get('ny',64)
        xlow,ylow = nx//2,ny//2
        xhigh,yhigh = nx-xlow,ny-ylow
        # size of the stamp is 64*64, so get an image of the same size, unless it's around the edge
        xcen_int,ycen_int = round(self.xcen-1),round(self.ycen-1) # zero-indexed
        self.slcx,self.slcy = (xcen_int-xlow,xcen_int+xhigh),(ycen_int-ylow,ycen_int+yhigh)
        self.slcx,self.slcy = np.clip(self.slcx,0,None),np.clip(self.slcy,0,None)
        return self.tim.subimage(*self.slcx,*self.slcy) # zero-indexed

    def draw(self, obj):
        """
        Return a :class:`GSImage` with ``obj`` in the center.

        If either ``obj.sersic`` or ``obj.shape_r`` is 0, a point source is drawn.
        Else a Sersic profile is used.

        Parameters
        ----------
        obj : SimCatalog row
            An object with attributes ``ra``, ``dec``, ``sersic``, ``shape_r``,
            ``shape_e1``, ``shape_e2``, ``'flux_%s' % self.band``.

        Returns
        -------
        gim : GSImage, None
            Image with ``obj`` if the stamp overlaps the tim, else None.
        """
        self.set_local(obj.ra,obj.dec)
        subimg = self.get_subimage()
        if not all(subimg.shape):
            return None
        flux = obj.get('flux_%s' % self.band)
        pos = tractor.RaDecPos(obj.ra,obj.dec)
        brightness = tractor.NanoMaggies(**{self.band:flux,'order':[self.band]})
        sersicindex = tractor.sersic.SersicIndex(obj.sersic)
        if (obj.shape_r==0.) or (obj.sersic==0):
            src = tractor.PointSource(pos,brightness)
        else:
            shape = tractor.EllipseESoft(np.log(obj.shape_r),obj.shape_e1,obj.shape_e2)
            src = tractor.sersic.SersicGalaxy(pos=pos,brightness=brightness,
                                       shape=shape,sersicindex=sersicindex)
            #if sersic==1: src = tractor.ExpGalaxy(pos=pos,brightness=brightness,shape=shape)
            #elif sersic==4: src = tractor.DevGalaxy(pos=pos,brightness=brightness,shape=shape)
            #else: raise ValueError('sersic = %s should be 1 or 4' % sersic)
        new = tractor.Tractor([subimg], [src])
        mod0 = new.getModelImage(0)
        gim = GSImage(mod0,xmin=self.slcx[0]+1,ymin=self.slcy[0]+1) # one-indexed
        return gim


class GalSimStamp(BaseSimStamp):
    """
    Extend :class:`BaseSimStamp` with generation of **galsim** source stamps.

    Attributes
    ----------
    scale : float
        Pixel scale.

    psf : GSImage
        PSF.

    offsetint : galsim.PositionI
        Integer position of object in subimage.

    offsetfrac : galsim.PositionD
        Fractional position of object in subimage.
    """

    def set_local(self, ra, dec):
        """
        Extend :meth:`BaseSimStamp.set_local` by setting pixel :attr:`scale`,
        :attr:`psf` and object integer and fractional positions :attr:`offsetint` and :attr:`offsetfrac`.

        Parameters
        ----------
        ra : float
            Right ascension (degree).

        dec : float
            Declination (degree).
        """
        # x,y coordinates start at +1
        super(GalSimStamp,self).set_local(ra,dec)
        #self.scale = self.tim.subwcs.pixscale_at(self.xcen,self.ycen)
        self.scale = self.tim.subwcs.pixel_scale()
        self.psf = GSImage(self.tim.psf.getPointSourcePatch(self.xcen,self.ycen).patch,scale=self.scale)
        self.psf = galsim.InterpolatedImage(self.psf)

        def frac(x):
            return abs(x-int(x))

        self.offsetint = galsim.PositionI(int(self.xcen),int(self.ycen))
        self.offsetfrac = galsim.PositionD(frac(self.xcen),frac(self.ycen))

    def draw(self, obj):
        """
        Return a :class:`GSImage` with ``obj`` in the center.

        If either ``obj.sersic`` or ``obj.shape_r`` is 0, a point source is drawn.
        Else a Sersic profile is used.

        Parameters
        ----------
        obj : SimCatalog row
            An object with attributes ``ra``, ``dec``, ``sersic``, ``shape_r``,
            ``shape_e1``, ``shape_e2``, ``'flux_'+self.band``.

        Returns
        -------
        gim : GSImage
            Image with ``obj``.
        """
        self.set_local(obj.ra,obj.dec)
        flux = obj.get('flux_%s' % self.band)
        gsparams = galsim.GSParams(maximum_fft_size=256**2)
        if (obj.shape_r==0.) or (obj.sersic==0):
            src = galsim.DeltaFunction(flux=flux,gsparams=gsparams)
        else:
            src = galsim.Sersic(obj.sersic,half_light_radius=obj.shape_r,flux=flux,gsparams=gsparams)
            src = src.shear(g1=obj.shape_e1,g2=obj.shape_e2)
        src = galsim.Convolve([src,self.psf])
        gim = src.drawImage(method='auto',scale=self.scale,
                            use_true_center=False,offset=self.offsetfrac)
        gim.setCenter(self.offsetint)
        return gim
