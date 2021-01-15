FROM legacysurvey/legacypipe:DR9.6.9

WORKDIR /src/

RUN apt -y update && apt install -y apt-utils && echo yes

RUN DEBIAN_FRONTEND=noninteractive \
  apt install -y --no-install-recommends \
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

RUN for x in \
  mpi4py \
  pandas \
  pytest \
  coverage \
  sphinx \
  sphinx-rtd-theme \
  galsim \
  ; do pip install $x; done \
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
RUN for tag in \
  DR9.6.2 \
  DR9.6.4 \
  DR9.6.5 \
  DR9.6.5b \
  DR9.6.6 \
  DR9.6.7 \
  DR9.6.7b \
  DR9.6.8 \
  DR9.6.9 \
  ; do mkdir "docker_$tag" ; done

COPY --from=legacysurvey/legacypipe:DR9.6.2 /usr/local/lib/python /src/legacypipe/py docker_DR9.6.2/
COPY --from=legacysurvey/legacypipe:DR9.6.2 /src/legacypipe/.git docker_DR9.6.2/legacypipe/.git

COPY --from=legacysurvey/legacypipe:DR9.6.4 /usr/local/lib/python /src/legacypipe/py docker_DR9.6.4/
COPY --from=legacysurvey/legacypipe:DR9.6.4 /src/legacypipe/.git docker_DR9.6.4/legacypipe/.git

COPY --from=legacysurvey/legacypipe:DR9.6.5 /usr/local/lib/python /src/legacypipe/py docker_DR9.6.5/
COPY --from=legacysurvey/legacypipe:DR9.6.5 /src/legacypipe/.git docker_DR9.6.5/legacypipe/.git

COPY --from=legacysurvey/legacypipe:DR9.6.5b /usr/local/lib/python /src/legacypipe/py docker_DR9.6.5b/
COPY --from=legacysurvey/legacypipe:DR9.6.5b /src/legacypipe/.git docker_DR9.6.5b/legacypipe/.git

COPY --from=legacysurvey/legacypipe:DR9.6.6 /usr/local/lib/python /src/legacypipe/py docker_DR9.6.6/
COPY --from=legacysurvey/legacypipe:DR9.6.6 /src/legacypipe/.git docker_DR9.6.6/legacypipe/.git

COPY --from=legacysurvey/legacypipe:DR9.6.7 /usr/local/lib/python /src/legacypipe/py docker_DR9.6.7/
COPY --from=legacysurvey/legacypipe:DR9.6.7 /src/legacypipe/.git docker_DR9.6.7/legacypipe/.git

COPY --from=legacysurvey/legacypipe:DR9.6.7b /usr/local/lib/python /src/legacypipe/py docker_DR9.6.7b/
COPY --from=legacysurvey/legacypipe:DR9.6.7b /src/legacypipe/.git docker_DR9.6.7b/legacypipe/.git

COPY --from=legacysurvey/legacypipe:DR9.6.8 /usr/local/lib/python /src/legacypipe/py docker_DR9.6.8/
COPY --from=legacysurvey/legacypipe:DR9.6.8 /src/legacypipe/.git docker_DR9.6.8/legacypipe/.git

COPY --from=legacysurvey/legacypipe:DR9.6.9 /usr/local/lib/python /src/legacypipe/py docker_DR9.6.9/
COPY --from=legacysurvey/legacypipe:DR9.6.9 /src/legacypipe/.git docker_DR9.6.9/legacypipe/.git

# legacypipe versions
RUN rm -rf legacypipe/py/obiwan \
  && (for tag in \
  DR9.6.2 \
  DR9.6.4 \
  DR9.6.5 \
  DR9.6.5-4-gbb698724 \
  DR9.6.6 \
  DR9.6.7 \
  DR9.6.7-75-g71be984c \
  DR9.6.8 \
  ; do cp -r legacypipe "legacypipe_$tag" && cd "legacypipe_$tag" && git checkout "tags/$tag" && cd .. ; done)

COPY . /src/legacysim
ENV PYTHONPATH /src/legacysim/py:${PYTHONPATH}

RUN python -O -m compileall legacysim/py/legacysim

WORKDIR /homedir/
