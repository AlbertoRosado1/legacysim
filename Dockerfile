FROM legacysurvey/legacypipe:DR10.3.3

WORKDIR /src/

RUN apt -y update && apt install -y apt-utils && echo yes

RUN apt install -y --no-install-recommends \
  openmpi-bin \
  mpich \
  gettext \
  texinfo \
  gawk \
  libeigen3-dev \
  cmake \
  # # Remove APT files
  && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN wget -nv http://www.fftw.org/fftw-3.3.8.tar.gz \
  && tar xvzf fftw-3.3.8.tar.gz \
  && cd fftw-3.3.8 \
  && ./configure --enable-shared \
  && make -j4 \
  && make install \
  && make clean \
  && cd .. && rm -Rf fftw-3.3.8 fftw-3.3.8.tar.gz

# Pip installs
RUN for x in \
    mpi4py \
    pandas \
    pytest \
    coverage \
    sphinx \
    sphinx-rtd-theme \
    galsim \
    ; do pip3 install --break-system-packages $x; done \
    && rm -Rf /root/.cache/pip

# desiutil
RUN git clone https://github.com/desihub/desiutil.git desiutil \
  && cd desiutil \
  && python3 setup.py install

# DUST maps
RUN mkdir -p dust/maps \
  && cd dust/maps \
  && wget -c https://portal.nersc.gov/project/cosmo/temp/dstn/travis-ci/maps/SFD_dust_4096_ngp.fits \
  && wget -c https://portal.nersc.gov/project/cosmo/temp/dstn/travis-ci/maps/SFD_dust_4096_sgp.fits
ENV DUST_DIR=/src/dust

# Get astrometry, tractor and legacypipe from previous docker images
# Ugly hack: also copy .git to get git versions at runtime
# RUN for tag in \
#  DR10.3 \
#  ; do mkdir "docker_$tag" ; done

#COPY --from=legacysurvey/legacypipe:DR10.3 /usr/local/lib/python /src/legacypipe/py docker_DR10.3/
#COPY --from=legacysurvey/legacypipe:DR10.3 /src/legacypipe/.git docker_DR10.3/legacypipe/.git

#COPY --from=legacysurvey/legacypipe:DR10.3.3 /usr/local/lib/python /src/legacypipe/py docker_DR10.3.3/
#COPY --from=legacysurvey/legacypipe:DR10.3.3 /src/legacypipe/.git docker_DR10.3.3/legacypipe/.git

# legacypipe versions
RUN rm -rf legacypipe/py/obiwan \
  && (for tag in \
  DR10.3 \
  ; do cp -r legacypipe "legacypipe_$tag" && cd "legacypipe_$tag" && git checkout "tags/$tag" && cd .. ; done)

COPY . /src/legacysim
ENV PYTHONPATH /src/legacysim/py:${PYTHONPATH}

RUN python -O -m compileall legacysim/py/legacysim

WORKDIR /homedir/
