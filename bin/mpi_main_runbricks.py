"""Run directly legacysim.runbrick.main."""

import os
from legacysim import RunCatalog,find_file,runbrick
from legacysim.batch import TaskManager,run_shell,get_pythonpath
import settings

ntasks = int(os.getenv('SLURM_NTASKS','1'))
threads = int(os.getenv('OMP_NUM_THREADS','1'))

#runcat = RunCatalog.from_input_cmdline(dict(brick=settings.get_bricknames(),fileid=settings.fileid,rowstart=settings.rowstart,skipid=settings.skipid))
runcat = RunCatalog.from_list(settings.runlist_fn)
runcat.seed = runcat.index()*42

with TaskManager(ntasks=ntasks) as tm:

    for run in tm.iterate(runcat):

        legacypipe_fn = find_file(base_dir=settings.legacypipe_output_dir,filetype='tractor',source='legacypipe',brickname=run.brickname)

        command = []
        for stage,versions in run.stages.items():
            pythonpath = 'PYTHONPATH=%s' % get_pythonpath(module_dir='/src/',versions=versions,full=True,as_string=True)
            command += [pythonpath]
            command += ['python',runbrick.__file__]
            command += ['--brick',run.brickname,'--threads',threads,'--outdir',settings.output_dir,'--run',settings.run,
                        '--ran-fn',settings.randoms_fn,'--fileid',run.fileid,'--rowstart',run.rowstart,
                        '--skipid',run.skipid,'--sim-blobs','--sim-stamp','tractor','--no-wise','--no-write',
                        '--seed',run.seed,'--stage',stage,
                        '--env-header',legacypipe_fn,';']

        run_shell(command)

        # if you do not care about package versions you can directly run runbrick.main() as below:
        #from legacysim.batch import EnvironmentManager
        #with EnvironmentManager(base_dir=settings.legacypipe_output_dir,brickname=run.brickname):

        #    command = ['--brick',run.brickname,'--threads',threads,'--outdir',settings.output_dir,'--run',settings.run,
        #                    '--ran-fn',settings.randoms_fn,'--fileid',run.fileid,'--rowstart',run.rowstart,
        #                    '--skipid',run.skipid,'--sim-blobs','--sim-stamp','tractor','--no-wise','--no-write',
        #                    #'--log',
        #                    '--ps','--ps-t0',int(time.time()),'--seed',run.seed]
        #
        #    print('Launching ' + ' '.join(map(str,command)))
        #
        #    runbrick.main(command)
