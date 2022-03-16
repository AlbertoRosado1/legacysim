import os
import sys
import importlib

from legacysim.survey import get_git_version
from legacysim.batch import EnvironmentManager


for docker, versions in EnvironmentManager._docker_versions:
    module_dir = '/src/docker_%s' % docker
    sys.path.insert(0, module_dir)
    for module in versions:
        if module == 'astrometry':
            version = importlib.reload(importlib.import_module(module)).__version__
        elif module == 'tractor':
            importlib.reload(importlib.import_module(module))
            version = importlib.reload(importlib.import_module('%s.version' % module)).version
        else:
            version = get_git_version(os.path.join(module_dir, module))
        if (docker, module, version) != ('DR9.6.7', 'astrometry', '0.83'): # in legacysim, 0.83 used for all DR9.6.7
            assert version == versions[module]
    print('All packages ok.')
