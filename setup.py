#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""Setup dot py."""
from __future__ import absolute_import, print_function

import re
from glob import glob
from os.path import basename, dirname, join, splitext

from setuptools import find_packages, setup


def read(*names, **kwargs):
    """Read description files."""
    path = join(dirname(__file__), *names)
    with open(path, encoding=kwargs.get('encoding', 'utf8')) as fh:
        return fh.read()


long_description = '{}\n{}'.format(
    re.compile(
        '^.. start-badges.*^.. end-badges',
        re.M | re.S,
        ).sub(
            '',
            read('README.rst'),
            ),
    re.sub(':[a-z]+:`~?(.*?)`', r'``\1``', read(join('CHANGELOG.rst')))
    )

setup(
    name='idpconfgen',
    version='0.0.4',
    description='Generates IDP conformers.',
    long_description=long_description,
    author='Julie Forman-Kay Lab',
    author_email='forman@sickkids.ca',
    url='https://github.com/julie-forman-kay-lab/IDPCalcPDBDownloader',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    py_modules=[splitext(basename(i))[0] for i in glob("src/*.py")],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list:
        # http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3.7',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        ],
    project_urls={
        'webpage': 'https://github.com/julie-forman-kay-lab/IDPCalcPDBDownloader',
        # 'Documentation': 'https://python-project-skeleton.readthedocs.io/',
        # 'Changelog': 'https://python-project-skeleton.readthedocs.io/en/latest/changelog.html',
        # 'Issue Tracker': 'https://github.com/joaomcteixeira/python-project-skeleton/issues',
        },
    keywords=[
        # eg: 'keyword1', 'keyword2', 'keyword3',
        ],
    python_requires='==3.7.*',
    install_requires=[
        'matplotlib>=3',
        'numpy>=1.7',
        # 'click',
        # eg: 'aspectlib==1.1.1', 'six>=1.7',
        ],
    extras_require={
        # eg:
        #   'rst': ['docutils>=0.11'],
        #   ':python_version=="2.6"': ['argparse'],
        },
    setup_requires=[
        #   'pytest-runner',
        #   'setuptools_scm>=3.3.1',
        ],
    entry_points={
        'console_scripts': [
            'idpconfgen = idpconfgen.cli:maincli',
            'icgpdbdl = idpconfgen.cli_pdbdownloader:maincli',
            ]
        },
    # cmdclass={'build_ext': optional_build_ext},
    # ext_modules=[
    #    Extension(
    #        splitext(relpath(path, 'src').replace(os.sep, '.'))[0],
    #        sources=[path],
    #        include_dirs=[dirname(path)]
    #    )
    #    for root, _, _ in os.walk('src')
    #    for path in glob(join(root, '*.c'))
    # ],
    )
