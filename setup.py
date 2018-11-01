#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division, print_function, unicode_literals, absolute_import

from setuptools import setup
import parmapper
setup(
    name='parmapper',
    py_modules=['parmapper'],
    long_description=open('readme.md').read(),
    version=parmapper.__version__,
    description='simple, robust, parallel mapping function',
    author='Justin Winokur',
    author_email='Jwink3101@@users.noreply.github.com',
    license='MIT'
)
