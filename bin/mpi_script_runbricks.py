"""Call ./runbrick.sh."""

import os
from legacysim import RunCatalog
from legacysim.batch import TaskManager,run_shell
import settings

ntasks = int(os.getenv('SLURM_NTASKS','1'))
threads = int(os.getenv('OMP_NUM_THREADS','1'))

runcat = RunCatalog.from_list(settings.runlist_fn)

with TaskManager(ntasks=ntasks) as tm:

    for run in tm.iterate(runcat):

        command = []
        for stage,versions in run.stages.items():
            command = ['./runbrick.sh']
            command += ['--brick',run.brickname,'--threads',threads,'--outdir',settings.output_dir,'--run',settings.run,
                        '--injected-fn',settings.injected_fn,'--fileid',run.fileid,'--rowstart',run.rowstart,
                        '--skipid',run.skipid,'--sim-blobs','--sim-stamp','tractor','--no-wise','--no-write','--stage',stage,
                        '--legpipedir',settings.legacypipe_output_dir,';']

        #print(command)
        output = run_shell(command)
        print('Output: ' + output)
