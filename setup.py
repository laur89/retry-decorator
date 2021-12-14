#!/usr/bin/env python

from os.path import exists
from setuptools import setup, find_packages

__plugin_name__ = 'retry-deco'
__author__ = 'Laur'
__version__ = '0.0.1'
__url__ = 'https://github.com/laur89/retry-decorator'
__license__ = 'MIT'
__description__ = 'Retry Decorator for py'

setup(
        name=__plugin_name__,
        version=__version__,
        description=__description__,
        author=__author__,
        url=__url__,
        license=__license__,
        scripts=[],
        packages=find_packages(),
        long_description=open('README.md').read() if exists('README.md') else __description__,
        python_requires='>=3.7',
        install_requires=[],
        classifiers=[
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3 :: Only',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Programming Language :: Python :: 3.9',
            'Programming Language :: Python :: 3.10',
        ]
)
