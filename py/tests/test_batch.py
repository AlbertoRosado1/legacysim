import os
import io
import sys
import shutil
import importlib

import numpy as np
import fitsio
import legacypipe
from legacypipe import runbrick as lprunbrick

from legacysim import setup_logging, runbrick, SimCatalog, RunCatalog, find_file
from legacysim.catalog import ListStages, Stages
from legacysim.batch import TaskManager, EnvironmentManager, environment_manager, run_shell, get_pythonpath
from legacysim.scripts import runlist


setup_logging()


def test_task_manager():

    with TaskManager(ntasks=1) as tm:
        lit = list(range(10))
        li = []
        for i in tm.iterate(lit):
            li.append(i)
        assert li == lit
        li = tm.map(lambda i: i+1,lit)
        assert li == list(range(1,len(lit)+1))


def test_environment_manager_runlist():
    # here we run legacypipe and legacysim for different configurations, using environment_manager and runlist scripts
    survey_dir = os.path.join(os.path.dirname(__file__), 'testcase3')
    # first create environment variables
    names_environ,shorts_environ = [],[]
    for name,short in EnvironmentManager._shorts_env.items():
        names_environ.append(name)
        shorts_environ.append(short)
    keys_version = ['LEGPIPEV'] + ['VER_%s' % short for short in EnvironmentManager._shorts_stage.values()]
    #keys_version.remove('VER_TIMS') # not in < DR9.6.7
    keys_version.remove('VER_WISE') # not run
    assert 'GAIA_CAT_DIR' in names_environ
    assert 'GAIA_CAT' in shorts_environ

    def get_environ(nwise=4,rng=None):
        if rng is None: rng = np.random.RandomState()
        toret = {}
        for iname,(name,short) in enumerate(EnvironmentManager._shorts_env.items()):
            toret[name] = '%s_%d' % (name,iname) # fake paths
        keys = []
        for name,key in EnvironmentManager._keys_env.items():
            if name == 'UNWISE_COADDS_DIR':
                tmp = []
                for i in range(nwise):
                    keys.append('UNWISD%d' % (i+1))
                    tmp.append('%s_%d' % (name,rng.randint(100)))
                toret[name] = ':'.join(tmp) # fake paths
            elif name not in ['UNWISE_MODEL_SKY_DIR']:
                keys.append(key)
                toret[name] = '%s_%d' % (name,rng.randint(100)) # fake paths
        toret['GAIA_CAT_DIR'] = os.path.join(survey_dir, 'gaia')
        return toret,keys

    # test versions
    modules = ['legacypipe']
    configs = {}
    configs['run1'] = {}
    configs['run1']['stages'] = [('writecat',{('legacypipe','DR9.6.7')})]
    configs['run1']['environ'] = get_environ(nwise=4)
    configs['run2'] = {}
    configs['run2']['stages'] = [('tims',{('legacypipe','DR9.6.5')}),('writecat',{('legacypipe','DR9.6.5')})]
    configs['run2']['environ'] = get_environ(nwise=2)
    configs['run3'] = {}
    configs['run3']['stages'] = [('halos',{('legacypipe','DR9.6.5')}),('writecat',{('legacypipe','DR9.6.5')})]
    configs['run3']['environ'] = get_environ(nwise=10)

    brickname = '2447p120'
    zoom = [1020,1070,2775,2815]

    runbrick_args = ['--brick', brickname, '--zoom', *map(str,zoom),
                    '--no-wise',
                    '--survey-dir', survey_dir,
                    '--threads', '1']

    module_dir = legacypipe.__file__
    for i in range(4): module_dir = os.path.dirname(module_dir)

    legacypipe_dir,pickle_dir,pickle_fn = {},{},{}
    pythonpath_modules = {}

    # clear os.environ for pytest
    for run,config in configs.items():
        for key in list(config['environ'][0].keys()) + ['GAIA_CAT_VER']:
            if key in os.environ: del os.environ[key]
        legacypipe_dir[run] = 'out-testcase3-legacypipe-%s' % run
        pickle_dir[run] = 'pickles_%s' % run
        pickle_fn[run] = os.path.join(pickle_dir[run],'runbrick-%(brick)s-%%(stage)s.pickle')
        for stage,versions in config['stages']:
            for module,version in versions:
                if module in ['legacypipe','legacysim']:
                    path = os.path.join(module_dir,'%s_%s' % (module,version),'py')
                    assert os.path.isdir(path)
                    pythonpath_modules[(module,version)] = path
                    # clear sys.path for pytest
                    if path in sys.path: sys.path.remove(path)

    environ = os.environ.copy()
    os.environ['GAIA_CAT_VER'] = '2'

    # first run legacypipe
    for run,config in configs.items():

        shutil.rmtree(pickle_dir[run],ignore_errors=True)
        assert not os.path.isdir(pickle_dir[run])

        os.environ.update(config['environ'][0])

        for stage,versions in config['stages']:
            for module,version in versions:
                path = pythonpath_modules[(module,version)]
                sys.path.insert(0,path)
                m = importlib.reload(importlib.import_module(module))
                assert m.__file__ == os.path.join(path,module,'__init__.py')

            args = runbrick_args + ['--outdir',legacypipe_dir[run],'--pickle',pickle_fn[run]]
            if stage == 'writecat':
                args += ['--no-write']
            else:
                args += ['--stage',stage]
            lprunbrick.main(args)

        shutil.rmtree(pickle_dir[run],ignore_errors=True)
        assert not os.path.isdir(pickle_dir[run])
        os.environ = environ.copy()

    def get_env(header,keys_environ):
        env = {}
        for key in header:
            if header[key] in shorts_environ:
                env[header[key]] = header[key.replace('DEPNAM','DEPVER')]
        # for DR9.6.2
        if 'VER_TIMS' not in header:
            header['VER_TIMS'] = header['LEGPIPEV']
        if 'LSV_TIMS' not in header and 'LEGSIMV' in header:
            header['LSV_TIMS'] = header['LEGSIMV']
        for key in keys_version + keys_environ:
            env[key] = header[key]
        return env

    def add_syspath(pythonpath):
        pythonpath = pythonpath.copy()
        for path in sys.path:
            if path not in pythonpath:
                pythonpath.append(path)
        sys.path = pythonpath

    # check EnvironmentManager works
    for irun,(run,config) in enumerate(configs.items()):

        shutil.rmtree(pickle_dir[run],ignore_errors=True)
        assert not os.path.isdir(pickle_dir[run])

        legacypipe_fn = find_file(base_dir=legacypipe_dir[run],filetype='tractor',source='legacypipe',brickname=brickname)
        header_legacypipe = fitsio.read_header(legacypipe_fn)
        #print(header_legacypipe)
        keys_environ = config['environ'][1]
        env_legacypipe = get_env(header_legacypipe,keys_environ=keys_environ)
        assert len(env_legacypipe) == len(shorts_environ) + len(keys_version) + len(keys_environ)
        for stage,versions in config['stages']:
            for module,version in versions:
                if module == 'legacypipe':
                    assert env_legacypipe['VER_%s' % EnvironmentManager._shorts_stage[stage]] == version
        tractor_legacypipe = SimCatalog(legacypipe_fn)

        output_dirs = []
        for i in range(1,5):
            output_dir = 'out-testcase3-legacysim-%d' % i
            shutil.rmtree(output_dir,ignore_errors=True)
            output_dirs.append(output_dir)

        for stage,version in config['stages']:

            # with pickle; if irun != 0, try legacysim default option which consists in saving pickle in legacysim file structure
            args = runbrick_args.copy()
            if irun == 0: args += ['--pickle',pickle_fn[run]]
            if stage == 'writecat':
                args += ['--no-write']
            else:
                args += ['--stage',stage]

            # environment from legacypipe tractor header
            with EnvironmentManager(base_dir=legacypipe_dir[run],brickname=brickname) as em:
                tmppythonpath = get_pythonpath(module_dir,[(module,em.get_module_version(module,stage=stage)) for module in modules],full=False)
                add_syspath(tmppythonpath)
                importlib.reload(legacypipe)
                runbrick.main(args=args + ['--outdir',output_dirs[0]])

            assert os.environ == environ

            # environment from legacysim tractor header
            with EnvironmentManager(base_dir=output_dirs[0],brickname=brickname,source='legacysim') as em:
                tmppythonpath = get_pythonpath(module_dir,[(module,em.get_module_version(module,stage=stage)) for module in modules],full=True)
                add_syspath(tmppythonpath)
                importlib.reload(legacypipe)
                runbrick.main(args=args + ['--outdir',output_dirs[1]])

            assert os.environ == environ

            # runbrick environment handling
            runbrick.main(args=args + ['--outdir',output_dirs[2]] + ['--env-header',legacypipe_fn])

            assert os.environ == environ

            args = ['--module-dir',module_dir,'--outdir',legacypipe_dir[run],'--brick',brickname,'--full-pythonpath']
            if stage != 'writecat': args += ['--stage',stage]

            old_stdout = sys.stdout
            sys.stdout = buffer = io.StringIO()
            environment_manager.main(args)
            sys.stdout = old_stdout
            env = buffer.getvalue().split('\n')[:-1] # last is empty string

            env_shell = run_shell(['python',environment_manager.__file__] + args + ['2> /dev/null']).split('\n')[:-1]
            assert env_shell[1:] == env[1:]
            pythonpath = env[0][len('PYTHONPATH='):].split(':')
            assert pythonpath == tmppythonpath

            # remove for pytest
            pythonpath = env_shell[0]
            assert pythonpath.startswith('PYTHONPATH=')
            pythonpath = pythonpath[len('PYTHONPATH='):].split(':')
            assert pythonpath == tmppythonpath

            for e in env_shell[1:]:
                key,val = e.split('=')
                assert config['environ'][0][key] == val

        shutil.rmtree(pickle_dir[run],ignore_errors=True)
        list_fn = 'runlist.txt'
        try:
            os.remove(list_fn)
        except OSError:
            pass
        assert runlist.main(['--outdir','.']) is None
        runcat = runlist.main(['--outdir',legacypipe_dir[run],'--modules'] + modules)
        assert runcat is not None
        assert not os.path.exists(list_fn)
        list_fn = os.path.join(output_dirs[3],'runlist.txt')
        run_shell(['python',runlist.__file__] + ['--outdir',output_dirs[0],'--source','legacysim','--write-list',list_fn,'--modules'] + modules)
        runcat2 = RunCatalog.from_list(list_fn)
        assert runcat2 == runcat
        os.remove(list_fn)
        runcat2 = runlist.main(['--outdir',legacypipe_dir[run],'--source','legacypipe'])
        assert np.all(runcat2.stagesid == 0) and runcat2.get_list_stages() == ListStages([Stages()]) # only writecat, no version

        for run in runcat:
            command = []
            for stage,versions in run.stages.items():
                tmppythonpath = 'PYTHONPATH=%s' % get_pythonpath(module_dir,versions,full=True,as_string=True)
                command += [tmppythonpath,'python',runbrick.__file__] + runbrick_args \
                            + ['--outdir',output_dirs[3],'--stage',stage,'--env-header',legacypipe_fn,';']
                #run_shell([tmppythonpath,'python',runbrick.__file__] + runbrick_args \
                #            + ['--outdir',output_dirs[3],'--stage',stage,'--env-header',legacypipe_fn])
            run_shell(command,check=True)
        # check same headers
        for iout,output_dir in enumerate(output_dirs):

            legacysim_fn = find_file(base_dir=output_dir,filetype='tractor',source='legacysim',brickname=brickname)
            header_legacysim = fitsio.read_header(legacysim_fn)
            env_legacysim = get_env(header_legacysim,keys_environ)
            assert env_legacypipe == env_legacysim
            tractor_legacysim = SimCatalog(legacysim_fn)
            if iout <= 2: assert tractor_legacysim == tractor_legacypipe

        #print(header_legacypipe)

def test_docker_versions():

    header_legacypipe = fitsio.read_header(find_file(base_dir='out-testcase3-legacypipe-run1',filetype='tractor',source='legacypipe',brickname='2447p120'))
    em = EnvironmentManager(header=header_legacypipe)

    for docker,versions in EnvironmentManager._docker_versions.items():
        split_stages = 3
        legacypipe_versions = {stage:versions['legacypipe'] for stage in Stages.all()[:split_stages]}
        legacypipe_versions.update({stage:'DR9.6.7' for stage in Stages.all()[split_stages:]})
        for module,version in versions.items():
            if module == 'legacypipe':
                for stage in Stages.all():
                    em.header['VER_%s' % EnvironmentManager._shorts_stage[stage]] = legacypipe_versions[stage]
            else:
                for k in em.header:
                    if k.startswith('DEPNAM') and em.header[k] == module:
                        em.header[k.replace('DEPNAM','DEPVER')] = version
                        break

        for stage in Stages.all():
            for module,version in versions.items():
                if module == 'legacypipe':
                    assert em.get_module_version(module=module,stage=stage) == legacypipe_versions[stage]
                else:
                    assert em.get_module_version(module=module,stage=stage) == version

        for istage,stage in enumerate(Stages.all()):
            if docker != 'DR9.6.7' and istage >= split_stages:
                assert em.get_module_version(module='docker',stage=stage) == 'DR9.6.7b'
            else:
                assert em.get_module_version(module='docker',stage=stage) == docker
