#!/usr/bin/env python

import glob
import os
import sys
from setuptools import setup, find_packages
setup_keywords = dict()

setup_keywords['name'] = 'legacysim'
setup_keywords['description'] = 'Monte Carlo simulation of the legacypipe'
setup_keywords['author'] = 'DESI Collaboration'
setup_keywords['author_email'] = ''
setup_keywords['license'] = 'BSD'
setup_keywords['url'] = 'https://github.com/adematti/legacysim'

#
# Setup.py, you suck
#setup_keywords['test_suite'] = 'nose.collector'
#setup_keywords['tests_require'] = ['nose']
#setup_keywords['test_suite'] = 'py/test'
#setup_keywords['test_suite'] = 'run_tests'
#
# Import this module to get __doc__ and __version__.
#
sys.path.insert(int(sys.path[0] == ''),'./py')
try:
    from importlib import import_module
    product = import_module(setup_keywords['name'])
    setup_keywords['long_description'] = product.__doc__

    from legacysim.survey import get_git_version
    version = get_git_version(os.path.dirname(__file__)).replace('-','.')

    setup_keywords['version'] = version
except ImportError:
    #
    # Try to get the long description from the README.rst file.
    #
    if os.path.exists('README.md'):
        with open('README.md') as readme:
            setup_keywords['long_description'] = readme.read()
    else:
        setup_keywords['long_description'] = ''
    sys.path.insert(int(sys.path[0] == ''),'./py/legacysim')
    from _version import __version__
    setup_keywords['version'] = __version__

#
# Set other keywords for the setup function.  These are automated, & should
# be left alone unless you are an expert.
#
# Treat everything in bin/*.{py,sh,slurm} as a script to be installed.
#
if os.path.isdir('bin'):
    setup_keywords['scripts'] = [fname for fname in glob.glob(os.path.join('bin', '*'))
        if os.path.basename(fname).split('.')[-1] in ['sh', 'py', 'slurm']]

setup_keywords['provides'] = [setup_keywords['name']]
setup_keywords['requires'] = ['Python (>2.7.0)']
#setup_keywords['install_requires'] = ['Python (>2.6.0)']
setup_keywords['zip_safe'] = False
setup_keywords['use_2to3'] = True
print('Finding packages...')
setup_keywords['packages'] = find_packages('py')
print('Done finding packages.')
setup_keywords['package_dir'] = {'':'py'}
setup_keywords['package_data'] = {'legacypipe': ['config/*', 'data/*'],
                                  'legacyzpts': ['data/*']}
#
# Run setup command.
#
setup(**setup_keywords)
