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

RUN rm -rf legacypipe/py/legacysim # to avoid having this legacysim version in the PYTHONPATH

# legacypipe versions
RUN for v in \
  DR9.6.2 \
  DR9.6.4 \
  DR9.6.5 \
  DR9.6.5-4-gbb698724 \
  DR9.6.6 \
  DR9.6.7 \
  DR9.6.7-75-g71be984c \
  DR9.6.8 \
  ; do cp -r legacypipe "legacypipe_$v" && cd "legacypipe_$v" && git checkout "tags/$v" && cd .. ; done

COPY . /src/legacysim
ENV PYTHONPATH /src/legacysim/py:${PYTHONPATH}

#RUN cd /src/legacysim/ \
#  && python3 setup.py install --home=/usr/local

WORKDIR /homedir/
