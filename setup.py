#!/usr/bin/env python

from os.path import exists
from setuptools import setup, find_packages

from retry_decorator import __version__

setup(
        name='retry-deco',
        version=__version__,
        author='Laur',
        scripts=[],
        url='https://github.com/laur89/retry-decorator',
        license='MIT',
        packages=find_packages(),
        description='Retry Decorator',
        long_description=open('README.rst').read() if exists("README.rst") else "",
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
