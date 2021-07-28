import os
import sys
import importlib

from legacysim.survey import get_git_version
from legacysim.batch import EnvironmentManager


for docker,versions in EnvironmentManager._docker_versions.items():
    module_dir = '/src/docker_%s' % docker
    sys.path.insert(0,module_dir)
    for module in versions:
        if module == 'astrometry':
            version = importlib.reload(importlib.import_module(module)).__version__
        elif module == 'tractor':
            importlib.reload(importlib.import_module(module))
            version = importlib.reload(importlib.import_module('%s.version' % module)).version
        else:
            version = get_git_version(os.path.join(module_dir,module))
        print(docker,module,version,versions[module])
        assert version == versions[module]
    print('All packages ok.')
