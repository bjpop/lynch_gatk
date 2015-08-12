#!/usr/bin/env python

from setuptools import setup

setup(
    name='complexo_pipeline',
    version='0.0.1',
    author='Bernie Pope',
    author_email='bjpope@unimelb.edu.au',
    packages=['src'],
    entry_points={
        'console_scripts': ['complexo_pipeline = src.main:main']
    },
    url='https://github.com/bjpop/complexo_pipeline',
    license='LICENSE.txt',
    description='complexo_pipeline is a pipeline system for bioinformatics workflows\
     with support for running pipeline stages on a distributed compute cluster.',
    long_description=open('README.md').read(),
    install_requires=[
        "ruffus == 2.6.3",
        "drmaa == 0.7.6",
        "PyYAML == 3.11"
    ],
)
