#!/bin/bash

# Script for running the legacysim code within a Shifter container at NERSC

# Don't add ~/.local/ to Python's sys.path
export PYTHONNOUSERSITE=1

# Force MKL single-threaded
# https://software.intel.com/en-us/articles/using-threaded-intel-mkl-in-multi-thread-application
export MKL_NUM_THREADS=1
export OMP_NUM_THREADS=1

# To avoid problems with MPI and Python multiprocessing
export MPICH_GNI_FORK_MODE=FULLCOPY
export KMP_AFFINITY=disabled

# Can detect Cori KNL node (96 GB) via:
# grep -q "Xeon Phi" /proc/cpuinfo && echo Yes

#cd /src/legacysim/py
cd ../py

# Defaults
outdir=${OUTPUT_DIR}
legpipedir=${LEGACYPIPE_DIR}
stage='writecat'
rowstart=0
skipid=0
fileid=0
threads=1
# Cmd line arguments
others=()

while [[ $# -gt 0 ]]
do
key="$1"
case $key in
  --brick)
  brick="$2"
  shift # past argument
  shift # past value
  ;;
  --outdir)
  outdir="$2"
  shift # past argument
  shift # past value
  ;;
  --legpipedir)
  legpipedir="$2"
  shift # past argument
  shift # past value
  ;;
  --fileid)
  fileid="$2"
  shift # past argument
  shift # past value
  ;;
  --rowstart)
  rowstart="$2"
  shift # past argument
  shift # past value
  ;;
  --skipid)
  skipid="$2"
  shift # past argument
  shift # past value
  ;;
  --stage)
  stage="$2"
  shift # past argument
  shift # past value
  ;;
  --threads)
  threads="$2"
  shift # past argument
  shift # past value
  ;;
  *)
  others+=" $1" # save it in an array for later
  shift # past argument
  ;;
esac
done

# 128 GB / Cori Haswell node = 134217728 kbytes, 32 cores
maxmem=134217728
let usemem=${maxmem}*${threads}/32

ulimit -Sv "$usemem"

mkdir -p "${output_dir}"

rsname="file${fileid}_rs${rowstart}_skip${skipid}"
bri=$(echo "$brick" | head -c 3)
logfn="${outdir}/logs/${bri}/${brick}/${rsname}/${brick}.log"
mkdir -p "${logfn%/*}"

echo "Logging to: $logfn"
echo "Running on $(hostname)"

env=($(python legacysim/batch/environment_manager.py --module-dir "/src/" --outdir "$legpipedir" --brick "$brick" --full-pythonpath 2> /dev/null))
for exp in ${env[@]}
do
  export "$exp"
done
if [ -z "$env" ]
then
  echo "WARNING: Environment not set"
fi

echo -e "\n\n\n" >> "$logfn"
echo "-----------------------------------------------------------------------------------------" >> "$logfn"
echo "PWD: $(pwd)" >> "$logfn"
echo >> "$logfn"
echo "Environment:" >> "$logfn"
set | grep -v PASS >> "$logfn"
echo >> "$logfn"
ulimit -a >> "$logfn"
echo >> "$logfn"

echo -e "\nStarting on $(hostname)\n" >> "$logfn"
echo "-----------------------------------------------------------------------------------------" >> "$logfn"

python -O legacysim/runbrick.py \
      --brick "$brick" \
      --outdir "${outdir}" \
      --fileid "${fileid}" \
      --rowstart "${rowstart}" \
      --skipid "${skipid}" \
      --stage "${stage}" \
      --threads "${threads}" \
      --ps \
      --ps-t0 "$(date "+%s")" \
      $others
      >> "$logfn" 2>&1
