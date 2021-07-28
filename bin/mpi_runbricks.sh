#!/bin/bash
# Set up the legacypipe environment
# and launch mpi_main_runbricks.py (default) or mpi_script_runbricks.py (option -s).

# add here legacysim to python path if necessary
#export PYTHONPATH=$HOME/legacysim/py:$PYTHONPATH

# set number of OpenMP threads here
export OMP_NUM_THREADS=8
source ./legacypipe-env.sh
chmod u+x ./runbrick.sh

type="main"

while [[ $# -gt 0 ]]
do
key="$1"
case $key in
  -s)
  type="script"
  shift # past value
  ;;
esac
done
if [ "$type" = "main" ]; then
  python mpi_main_runbricks.py
else
  python mpi_script_runbricks.py
fi
