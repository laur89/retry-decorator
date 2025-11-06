from os.path import exists
from setuptools import setup, find_packages

__package_name__ = 'retry-deco'
__author__ = 'Laur'
__url__ = 'https://github.com/laur89/retry-decorator'
__license__ = 'MIT'
__description__ = 'Retry Decorator for py'

readme_f = 'README.md'

setup(
        name=__package_name__,
        version='1.1.2.dev0',  # managed by zest.releaser!
        description=__description__,
        author=__author__,
        url=__url__,
        license=__license__,
        scripts=[],
        packages=find_packages(),
        # long_description=open(readme_f).read() if exists(readme_f) else __description__,
        python_requires='>=3.7',
        install_requires=[],
        classifiers=[
            'Programming Language :: Python :: 3',
        ]
)
