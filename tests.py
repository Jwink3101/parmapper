#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Some simple tests. Some of these are rough without exact expected results.
"""
from __future__ import division, print_function, unicode_literals

import parmapper
parmapper.set_start_method()

import multiprocessing as mp
import time

if parmapper.CPU_COUNT < 2:
    raise ValueError('Tests require 2+ cores')

class Timer:
    """
    Time the *single* execution of the statement. Use as a contex manager:
    
        with timeit():
            do_stuff()
        
    Or as a decorator
    
        @timeit() # must have ()
        def do_stuff():
            do_more_stuff
            
    """
    def __init__(self,verbose=True):
        self.verbose=verbose
    def __enter__(self,*a,**k):
        self.t0 = time.time()
        return self
    def __exit__(self,*args):
        self.t1 = time.time()
        self.elapsed = self.t1 - self.t0
        if self.verbose:
            print('\nElasped Time: {:0.5g} s'.format(self.elapsed))

LOCK = mp.Lock()
def sleep(ii,t=0.05):
    time.sleep(t)
    with LOCK:
        print(ii,t,end=' ')
    return ii


print('--- Regular ---')
with Timer():
    list(map(sleep,range(10)))
with Timer():
    list(parmapper.parmap(sleep,range(10),N=2))
with Timer():
    list(parmapper.parmap(sleep,range(10),N=4))

print('--- Set KW fixed ---')
# Set the elapsed time. From now on, use parmap with N=1
for N in [1,2,4]:
    with Timer():
        list(parmapper.parmap(sleep,range(10),N=N,kwargs={'t':0.01}))

print('--- Set KW as args fixed ---')
# Set the elapsed time. From now on, use parmap with N=1
for N in [1,2,4]:
    with Timer():
        list(parmapper.parmap(sleep,range(10),N=N,args=(0.01,) ))

print('--- Set KW varied ---')
# Set the elapsed time. From now on, use parmap with N=1
for N in [1,2,4]:
    with Timer():
        list(parmapper.parmap(sleep,((i,{'t':i/40.0}) for i in range(10)),N=N,
                           kwstar=True))
print('--- Set KW as arg varied ---')
# Set the elapsed time. From now on, use parmap with N=1
for N in [1,2,4]:
    with Timer():
        list(parmapper.parmap(sleep,((i,i/40.0) for i in range(10)),N=N,
                           star=True))


def addsleep(ii,jj,t=0.05):
    time.sleep(t)
    with LOCK:
        print(ii,jj,t,end=' ')
    return ii+jj
rgold = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

print('--- star ---')
for N in [1,2,4]:
    with Timer():
        r = list(parmapper.parmap(addsleep,zip(range(10),range(10)),
                               N=N,star=True))
        assert r == rgold
print('--- star with kw time ---')
for N in [1,2,4]:
    with Timer():
        r = list(parmapper.parmap(addsleep,zip(range(10),range(10)),
                               N=N,star=True,kwargs={'t':0.01}))
        assert r == rgold
print('--- star with kw time as arg ---')
for N in [1,2,4]:
    with Timer():
        r = list(parmapper.parmap(addsleep,zip(range(10),range(10)),
                               N=N,star=True,args=(0.01,)))
        assert r == rgold
        
print('--- star with kwstar time varied ---')
for N in [1,2,4]:
    with Timer():
        args = zip(range(10),range(10))
        kwargs = [{'t':i/40.0} for i in range(10)]
        r = list(parmapper.parmap(addsleep,zip(args,kwargs),
                               N=N,star=True,kwstar=True))
        assert r == rgold
print('--- star with arg time varied via star ---')
for N in [1,2,4]:
    with Timer():
        args = zip(range(10),range(10),[i/40.0 for i in range(10)])
        r = list(parmapper.parmap(addsleep,args,
                               N=N,star=True))
        assert r == rgold
print('--- star with kwstar time varied OVERRIDE kwarg ---')
for N in [1,2,4]:
    with Timer():
        args = zip(range(10),range(10))
        kwargs = [{'t':i/40.0} for i in range(10)]
        r = list(parmapper.parmap(addsleep,zip(args,kwargs),
                               N=N,star=True,kwstar=True,
                               kwargs={'t':1}))

print('--- Threads ---')
# time.sleep releases the GIL so this should be about the same.
for N in [1,2,4]:
    with Timer():
        list(parmapper.parmap(sleep,range(10),N=1,Nt=N,kwargs={'t':0.01}))

print('--- Lambdas ---')
# Make sure this (a) runs and (b) returns properly
assert list(parmapper.parmap(lambda a:a,range(10),N=2)) == list(range(10))
assert list(parmapper.parmap(lambda a,b:a+b,zip(range(10),range(10)),
                         star=True,N=2)) == [2*a for a in range(10)]
assert list(parmapper.parmap(lambda a,b=2:a+b,range(10),
                          N=2)) == [a+2 for a in range(10)]
assert list(parmapper.parmap(lambda a,b=2:a+b,range(10),
                          N=2,kwargs={'b':3})) == [a+3 for a in range(10)]
assert list(parmapper.parmap(lambda a,b=2:a+b,zip(range(10),
                                              [{'b':i} for i in range(10)]),
                          N=2,kwstar=True)) == [2*a for a in range(10)]
assert list(parmapper.parmap(lambda a,b,c=2:a+b+c,zip(zip(range(10),range(10)),
                                                  [{'c':i} for i in range(10)]),
                          N=2,kwstar=True,star=True)) == [3*a for a in range(10)]














