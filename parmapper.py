#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
parmap (or parmapper): Tool for easy parallel function mapping
without requiring a pickleable function (e.g. lambdas).
"""
from __future__ import print_function, unicode_literals, division

__version__ = '20220211.0'

import multiprocessing as mp
import multiprocessing.dummy as mpd
from threading import Thread
import threading
import sys,os
from collections import defaultdict
import warnings
import math

try:
    from queue import Queue
except ImportError:
    from Queue import Queue

try:
    import tqdm
except ImportError:
    tqdm = None

from functools import partial

if sys.version_info[0] > 2:
    unicode = str
    xrange = range
    imap = map
else:
    from itertools import imap

CPU_COUNT = mp.cpu_count()

class _Exception(object):
    """Storage of an exception (and easy detection)"""
    def __init__(self,E,infun=True):
        self.E = E
        self.infun = infun

def parmap(fun,seq,
           N=None,Nt=1,
           chunksize=1,
           ordered=True,
           daemon=True,
           progress=False,
           total=None,
           args=(),kwargs=None,
           star=False,kwstar=False,
           exception=None):
    """
    parmap -- Simple parallel mapper that can split amongst processes (N)
              and threads (Nt) (within the processes).

              Does *NOT* require functions to be pickleable (unlike
              vanilla multiprocess.Pool.map)

    Inputs:
    -------
    fun
        Single input function. Use lambdas or functools.partial
        to enable/exapnd multi-input. See example

    seq
        Sequence of inputs to map in parallel

    Options:
    --------
    N [None] (integer or None)
        Number of processes to use. If `None`, will use the CPU_COUNT

    Nt [1] (integer)
        Number of threads to use. See notes below on multi-threaded vs
        multi-processes.

    chunksize [1] (int)
        How to be break up the incoming sequence. Useful if also using threads.
        Will be (re)set to max(chunksize,Nt). 
        
        Alternativly, if len(seq) exists and chunksize=-1 it will be reset
        to ceil(len(seq)/(N*Nt)). If chunksize=-1 and len(sequence) is not
        known, a warning will be emitted and chucksize will be reset to 
        max(chunksize,Nt)

    ordered [True] (bool)
        Whether or not to order the results. If False, will return in whatever
        order they finished.

    daemon [True] (bool)
        Sets the multiprocessing `daemon` flag. If  True, can not spawn child
        processes (i.e. cannot nest parmap) but should allow for CTRL+C type
        stopping. Supposedly, there may be issues with CTRL+C with it set to
        False. Use at your own risk

    progress [False] (bool or str)
        Display a progress bar or counter. If str, will be used as the text.
    
    total [None]
        Total number of items. If None (default) will try to use len(seq) if possible.
        If not possible, will still work!
    
    args [tuple()]
        Specify additional arguments for the function. They are added *after*
        the input argument
    
    kwargs [dict()]
        Specify additional keyword arguments

    star [False]
        If True, the arguments to the function will be "starred" so, for example
        if `seq = [ (1,2), (3,4) ]`, the function will be called as
            star is False: fun((1,2))
            star is True:  fun(1,2) <==> fun(*(1,2))
        Can also set to None to not send anything
        
    kwstar [False]
        Assumes all items are (vals,kwvals) where `vals` RESPECTS `star` 
        setting and still includes `args` and `kwvals`. See "Additional 
        Arguments" section below.
    
    exception ['raise' if N>1 else 'proc']
        Choose how to handle an exception in a child process
        
        'raise'     : [Default] raise the exception (outside of the Process). 
                      Also terminates all existing processes.
        'return'    : Return the Exception instead of raising it.
        'proc'      : Raise the exception inside the process. NOT RECOMMENDED
                      unless used in debugging (and with N=1)
        
        Note: An additional attribute called `seq_index` will also be set
              in the exception (whether raised or returned) to aid in debugging.
        
    Additional Arguments
    --------------------
    As noted above, there are many ways to pass additional arguments to
    your function. All of these are not completely needed since parmap
    makes using lambdas so easy, but they are there if preffered.
    
    Assume the following function:
    
        def dj(dictA,dictB):
            '''Join dictA and dictB where dictB takes precedence'''
            dictA = dictA.copy()
            dictA.update(dictB) # NOTE: dictB takes precedence
            return dictA

    Then the behavior is as follows where `args` and `kwargs` come from
    they main function call. The `val` (singular), `vals` (sequence/tuple of 
    values), and `kwvals` are set via the sequence.
    
    | star  | kwstar | expected   | args           | kw args             |   |
    |-------|--------|------------|----------------|---------------------|---|
    | False | False  | val        | *((val,)+args) | **kwargs            | A |
    | True  | False  | vals       | *(vals+args)   | **kwargs            |   |
    | None  | False  | ---        | *args          | **kwargs            | B |
    | None  | True   | ---        | *args          | **dj(kwargs,kwvals) | C |
    | False | True   | val,kwval  | *((val,)+args) | **dj(kwargs,kwvals) | C |
    | True  | True   | vals,kwval | *(vals+args)   | **dj(kwargs,kwvals) | C |
                                                        
                A: Default
                B: If kwargs and args are empty, basically calls with nothing
                C: Note the ordering so kwvals takes precedance

    Note:
    -----
    Performs SEMI-lazy iteration based on chunksize. It will exhaust the input
    iterator but will yield as results are computed (This is similar to the
    `multiprocessing.Pool().imap` behavior)

    Explicitly wrap the parmap call in a list(...) to force immediate
    evaluation

    Threads and/or Processes:
    -------------------------
    This tool has the ability to split work amongst python processes
    (via multiprocessing) and python threads (via the multiprocessing.dummy
    module). Python is not very performant in multi-threaded situations
    (due to the GIL) therefore, processes are the usually the best for CPU
    bound tasks and threading is good for those that release the GIL (such
    as IO-bound tasks). 
    
    WARNING: Many NumPy functions *do* release the GIL and can be threaded, 
             but many NumPy functions are, themselves, multi-threaded.

    Alternatives:
    -------------
    This tool allows more data types, can split with threads, has an optional
    progress bar, and has fewer pickling issues, but these come at a small cost. 
    For simple needs, the following may be better:

    >>> import multiprocessing as mp
    >>> with mp.Pool(N) as pool:
    >>>     results = list( pool.imap(fun,seq) ) # or just pool.map
    
    Start Methods:
    --------------
    * This tool is NOT compatible with Windows, just macOS (see below) 
      and Linux
      
    * on macOS, starting with python3.8, the start method must be explicity set
      when python starts up. See the [1] for details.
      
          >>> import multiprocessing as mp
          >>> mp.set_start_method('fork')
    
      If this has already been set, it will throw a RuntimeError.
      
      Alternativly, call the parmap(per).set_start_method()
    
      Or, set the PYTOOLBOX_SET_START=true as an enviorment variable and this
      will be set on module load. For example,
      
          export PYTOOLBOX_SET_START=true
    
      Also, set the following to prevent issues [2][3]
    
          export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

    to your .bashrc
    
    [1]: https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods 
    [2]: https://www.wefearchange.org/2018/11/forkmacos.rst.html
    [3]: https://stackoverflow.com/q/50168647/3633154
    
    Additional Note
    ---------------
    For the sake of convienance, a `map = imap = __call__` and
    `close = lamba *a,**k:None` are also added so a parmap function can mimic
    a multiprocessing pool object with duck typing

    Version:
    -------
    __version__
    
    """
    # Additional Notes:
    # This currently assumes the starting behavior of multiprocessing for
    # python 3.8. When 3.9 is released, it may have to be updated again.
    if sys.platform.lower().startswith('win'):
        raise RuntimeError('Not compatible with Windows')
        
    if sys.platform.startswith('darwin') and \
       sys.version_info >= (3,8) and \
       mp.get_start_method(allow_none=True) != 'fork':
        raise RuntimeError("Must set multiprocessing start_method to 'fork'. "
                           "Use `set_start_method` or see documentation")
    
    # Build up a dummy function with args,vals,kwargs, and kwvals
    if kwargs is None:
        kwargs = {}

    def _fun(ss):
        _args = list(args)
        _kw = kwargs.copy()
        try:
            # Check for None before boolean
            if star is None and kwstar:         # 4
                _kw.update(ss)
            elif star is None and not kwstar:   # 3
                pass
            elif not star and not kwstar:       # 1
                _args = [ss] + _args
            elif star and not kwstar:           # 2
                _args = list(ss) + _args    
            elif not star and kwstar:           # 5
                _args = [ss[0]] + _args
                _kw.update(ss[1])
            elif star and kwstar:               # 6
                _args = list(ss[0]) + _args
                _kw.update(ss[1])
            else:
                raise TypeError()
            
        except TypeError: # Mostly because bad input types
            return _Exception(TypeError('Ensure `args` are tuples and `kwargs` are dicts'),infun=False)
        except Exception as E:
            return _Exception(E,infun=False)
        
        if exception == 'proc':
            return fun(*_args,**_kw) # Outside of a try
        try:
            return fun(*_args,**_kw)
        except Exception as E:
            return _Exception(E)
            # It would be great to include all of sys.exc_info() but tracebacks
            # cannot be pickled.
    
    if total is None:   
        try:
            total = len(seq)
        except TypeError:
            total = None

    N = CPU_COUNT if N is None else N
        
    if exception is None:
        exception = 'raise' if N>1 else 'proc'

    if chunksize == -1:
        if total is None:
            warnings.warn('chunksize=-1 does not work when len(seq) is not known')
        else:
            chunksize = math.ceil(total/(N*Nt))
    chunksize = max(chunksize,Nt) # Reset

    # Consider resetting N
    if total is not None:
        N = min(N,total//chunksize)
        N = 1 if N < 1 else N

    # Build a counter iterator based on settings and tqdm
    
    if progress is True: # Set to str iff true but not named
        progress='parmap: '
        
    if tqdm is None:
        counter = partial(_counter,total=total,text=progress)
    else:
        counter = partial(tqdm.tqdm,total=total,desc=progress) # Set the total since tqdm won't be able to get it.
    
    # Handle N=1 without any multiprocessing
    if N == 1:
        try:
            if Nt == 1:
                out = imap(_fun,seq)
            else:
                pool = mpd.Pool(Nt)      # thread pools don't have the pickle issues
                out = pool.imap(_fun,seq)

            if progress:
               out = counter(out)
            for count,item in enumerate(out):
                if isinstance(item,_Exception):
                    item.E.seq_index = count # Store the index where this happened
                    if not item.infun:
                        exception = 'raise' # reset
                    if exception == 'raise':
                        raise item.E
                    elif exception == 'return':
                        item = item.E
                    elif exception == 'proc':
                        pass
                    else:
                        raise ValueError("Unrecognized `exception` setting '{}'".format(exception))
                yield item
        finally:
            if Nt > 1:
                pool.close()
        return
    
    q_in = mp.JoinableQueue() # Will need to `join` later to make sure is empty
    q_out = mp.Queue()
    workers = [mp.Process(target=_worker, args=(_fun, q_in, q_out,Nt)) for _ in range(N)]

    # Create a separate thread to add to the queue in the background
    def add_to_queue():
        for iixs in _iter_chunks(enumerate(seq),chunksize):
            q_in.put(iixs)

        # Once (if ever) it is exhausted, send None to close workers
        for _ in xrange(N):
            q_in.put(None)
    
    # Define a generator that will pull from the q_out and then run through
    # the rest of our generator/iterator chain for progress and ordering
    def queue_getter():
        finished = 0
        count = 0
        while finished < N:
            out = q_out.get()
            if out is None:
                finished += 1
                continue
            for o in out: # yield from out
                yield o
    try:
        # Start the workers
        for worker in workers:
            worker.daemon = daemon
            worker.start()
    
        add_to_queue_thread = Thread(target=add_to_queue)
        add_to_queue_thread.start()
    
        # Chain generators on output
        out = queue_getter()
        if progress:
            out = counter(out)

        if ordered:
            out = _sort_generator_unique_integers(out,key=lambda a:a[0])

        # Return items
        for item in out:
            count = item[0]
            item = item[1]
            if isinstance(item,_Exception):
                item.E.seq_index = count
                if not item.infun:
                    exception = 'raise' # reset
                
                if exception == 'raise':
                    for worker in workers: 
                        worker.terminate()
                    raise item.E
                elif exception == 'return':
                    item = item.E
                elif exception == 'proc':
                    pass
                else:
                    for worker in workers: 
                        worker.terminate()
                    raise ValueError("Unrecognized `exception` setting '{}'".format(exception))
            yield item
    finally:
        # Clean up threads and processes. Make sure the queue is exhausted
        add_to_queue_thread.join() # Make sure we've exhausted the input
        q_in.join() # Make sure there is nothing left in the queue
        for worker in workers:
            worker.join() # shut it down

# Add dummy methods
parmap.map = parmap.imap = parmap.__call__
parmap.close = lambda *a,**k: None

parmap.__doc__ = parmap.__doc__.replace('__version__',__version__)

parmapper = parmap # Rename

class ReturnProcess(mp.Process):
    """
    Like a regular multiprocessing Process except when you `join`, it returns 
    the function result. And it assumes a target is always passed. Also returns
    itself with start() to make simpler
    
    Inputs:
    -------
    target
        Function target
        
    exception ['raise']
        Choose how to handle an exception in a child process
        
        'raise'     : [Default] raise the exception (outside of the Process). 
        'return'    : Return the Exception instead of raising it.
        'proc'      : Raise the exception inside the process. NOT RECOMMENDED
    
    Usage:
    ------
    Replace: 
        >>> res1 = slow(arg1,kw=arg2)
        >>> res2 = slower(arg3,kw=arg4)
    
    with
        >>> p1 = ReturnProcess(slow,args=(arg1,),kwargs={'kw':arg2}).start()
        >>> p2 = ReturnProcess(slower,args=(arg3,),kwargs={'kw':arg4}).start()
        >>> res1 = p1.join()
        >>> res2 = p2.join()
    
    So one line becomes 2 (or 3) but they can happen at the same time
    """
    def __init__(self,target=None,exception='raise',**kwargs):
        if not target:
            raise ValueError('Must specify a target')
        if exception not in {'raise','return','proc'}:
            raise ValueError("exception must be in {'raise','return','proc'}")
        self.exception = exception
        
        self.target = target
        self.parent_conn,self.child_conn = mp.Pipe(duplex=False)
        super(ReturnProcess, self).__init__(target=self._target,**kwargs)
    
    def _target(self,*args,**kwargs):
        
        if self.exception == 'proc':
            res = self.target(*args,**kwargs)       
        else:
            try:
                res = self.target(*args,**kwargs)
            except Exception as E:
                res = _Exception(E)
        
        self.child_conn.send(res)
    
    def start(self):
        super(ReturnProcess, self).start()
        return self
    
    def join(self,**kwargs):
        super(ReturnProcess, self).join(**kwargs)
        res = self.parent_conn.recv()
        if not isinstance(res,_Exception):
            return res
    
        if self.exception == 'raise':
            raise res.E
        else: # return
            return res.E

def _counter(items,total=None,text=''):
    for ii,item in enumerate(items):
        if total is not None:
            _txtbar(ii,total,ticks=50,text=text)
        else:
            txt = '{}: {}'.format(text,ii+1)
            print('\r%s' % txt,end='')
            sys.stdout.flush()
        yield item


def _worker(fun,q_in,q_out,Nt):
    """ This actually runs everything including threadpools"""
    if Nt > 1:
        pool = mpd.Pool(Nt)
        _map = pool.map # thread pools don't have the pickle issues
    else:
        _map = map

    while True:
        iixs = q_in.get()
        if iixs is None:
            q_out.put(None)
            q_in.task_done()
            break
        def _ap(ix):
            i,x = ix
            return i, fun(x)
        res = tuple(_map(_ap,iixs)) # list forces the iteration
        q_out.put(res)
        q_in.task_done()

    if Nt >1:
        pool.close()

def _iter_chunks(seq,n):
    """
    yield a len(n) tuple from seq. If not divisible, the last one would be less
    than n
    """
    _n = 0;
    for item in seq:
        if _n == 0:
            group = [item]
        else:
            group.append(item)
        _n += 1

        if _n == n:
            yield tuple(group)
            _n = 0
    if _n > 0:
        yield tuple(group)

def _sort_generator_unique_integers(items,start=0,key=None):
    """
    Yield from `items` in order assuming UNIQUE keys w/o any missing!

    The items ( or key(item) ) MUST be an integer, without repeats, starting
    at `start`
    """
    queue = dict()
    for item in items:
        if key is not None:
            ik = key(item)
        else:
            ik = item

        if ik == start:
            yield item
            start += 1

            # Get any stored items
            while start in queue:
                yield queue.pop(start) # average O(1), worse-case O(N)
                start += 1             # but based on ref below, should be O(1)
        else:                          # for integer keys.
            queue[ik] = item           # Ref: https://wiki.python.org/moin/TimeComplexity

    # Exhaust the rest
    while start in queue:
        yield queue.pop(start)
        start += 1

def _txtbar(count,N,ticks=50,text='Progress'):
    """
    Print a text-based progress bar.

    Usage:
        _txtbar(count,N)

    Inputs:
        count   : Iteration count (start at 0)
        N       : Iteration size
        ticks   : [50] Number of ticks
        text    : ['Progress'] Text to display (don't include `:`)

    Prints a text-based progress bar to the terminal. Obviosly
    printing other things to screen will mess this up:
    """

    count = int(count+1)
    ticks = min(ticks,N)
    isCount = int(1.0*count%round(1.0*N/ticks)) == 0
    
    if not (isCount or count == 1 or count == N):
        return

    Npound = int(round(1.0 * count/N*ticks));
    Nspace = int(1.0*ticks - Npound);
    Nprint = int(round(1.0 * count/N*100));

    if count == 1:
        Nprint = 0
    if len(text)>0:
        text +=': '

    txt = '{:s}{:s}{:s} : {:3d}%  '.format(text,'#'*Npound,'-'*Nspace,Nprint)
    print('\r%s' % txt,end='',file=sys.stderr)
    sys.stderr.flush()

technical_details = """\
This code uses iterators/generators to handle and distribute the workload.
By doing this, it is easy to have all results pass through a common
counting function for display of the progress without the use of
global (multiprocessing manager) variables and locks.

With the exception of when N == 1 (where it falls back to serial methods)
the code works as follows:

- A background thread is started that will iterate over the incoming sequence
  and add items to the queue. If the incoming sequence is exhausted, the
  worker sends kill signals into the queue. The items are also chunked and 
  enumerated (used later to sort).
- After the background thread is started a function to pull from the OUTPUT
  queue is created. This counts the number of closed processes but otherwise
  yields the computed result items
- A pool of workers is created. Each worker will read from the input queue
  and distribute the work amongst threads (if using). It will then
  return the resuts into a queue
- Now the main work happens. It is done as chain of generators/iterators.
  The background worker has already begin adding items to the queue so
  now we work through the output queue. Note that this is in serial
  since the work was already done in parallel
        - Generator to pull from the result queue
        - Generator to count and display progress (if progress=True).
        - Generator to hold on to and return items in a sorted manner
          if sorting is requested. This can cause itermediate results to be
          stored until they can be returned in order
- The output generator chain is iterated pulling items through and then
  are yielded.
- cleanup and close processes (if/when the input is exhausted)
"""

np = None # will be imported when a ParEval is instantiated

class ParEval(object):
    """
    Evaluate the *vectorized* fun(X) (where X is a numpy array) in chunks 
    using parmap. If fun(X) is not vectorized, use the regular parmap
    
    Requires numpy
    
    Usage:
    ------
    
    Given a function `fun(X)` where X is a NumPy Array (such as N,ndim sample),
    a parallel version is ParEval(fun).
    
    To directly evaluate with X, do ParEval(fun)(X). 
    
    The advantage of returning a callable object rather than this being a 
    function is that there is no need to use functool.partial if you want to 
    pass the parallelized function to another.
    
    Inputs:
    -------
    fun
        Function to call. Use parmap keywords (e.g. args,kwargs,star) to
        add and/or control function call.
    
    Specify one of
        n_chunks
            How many chunks to split it up into
            
        n_eval
            How many evaluations per chunk (and split accordingly). Will be
            the upper limit.
            
        if neither is specified, then n_chunks is set to CPU_COUNT
    
    Options:
    -------
    n_min [0]
        Minimum size for a chunk. Will also override n_eval if needed 
        (since n_eval gets convered to n_chunks)
        
    All additional options are passed to parmap   
    
    Splits along the first axis.
    """
    
    def __init__(self,fun,n_chunks=None,n_eval=None,n_min=0,**kwargs):
        global np
        if np is None:
            import numpy as np
        
        self.fun = fun
        if (n_chunks is not None) and (n_eval is not None):
            raise ValueError('Must specify EITHER n_chunks OR n_eval')
        if n_chunks is None and n_eval is None:
            n_chunks = CPU_COUNT
        self.n_chunks = n_chunks
        self.n_eval = n_eval
        
        kwargs['chunksize'] = 1
        
        self.n_min = n_min
        self.kwargs = kwargs
        
    def __call__(self,X):
        chunker = _chunker(X,n_chunks=self.n_chunks,
                             n_eval=self.n_eval,
                             n_min=self.n_min)
        res = list(parmap(self.fun,chunker,**self.kwargs))
        return np.concatenate(res)
        
class _chunker(object):
    """Object to actually break into chunks and has a __len__"""
    def __init__(self,X,n_chunks=None,n_eval=None,n_min=0):
        global np
        if np is None:
            import numpy as np
        self.X = X = np.atleast_1d(X)
        n = len(X)
        # Get number of chunks
        if n_eval is not None:
            n_eval = max(n_min,n_eval)
            n_chunks = int(np.ceil(n/n_eval))
        if n_chunks is not None:
            n_chunks = n_chunks
            if n // n_chunks < n_min:
                n_chunks = n // n_min
        
        stops = np.asarray([n // n_chunks]*n_chunks,dtype=int)
        stops[:n % n_chunks] += 1
        self.stops = stops = np.cumsum(stops).tolist()
        self.len = len(stops)
    
        self.ii = 0
    
    def __next__(self):
        ii = self.ii
        if ii == self.len:
            raise StopIteration()
        a = 0 if ii == 0 else self.stops[ii-1]
        b = self.stops[ii]
        self.ii += 1
        return self.X[a:b]
    next = __next__
    def __iter__(self):
        return self

    def __len__(self):
        return self.len

def set_start_method():
    if sys.version_info < (3,8):
        return
    if mp.get_start_method(allow_none=True) != 'fork':
        try:
            mp.set_start_method('fork')
        except RuntimeError:
            raise RuntimeError('Cannot change startmethod. Restart Python and try again')

if os.environ.get('PYTOOLBOX_SET_START','false').lower() == 'true' \
   and sys.version_info >= (3,8) \
   and sys.platform.startswith('darwin'):
    set_start_method()
    import logging
    logging.debug("Set start method on darwin to 'fork'")
    
################################################################################
################################################################################
## Below is a simpler version of parmap. It really only serves the purpose of 
## being used to copy/paste when a short-and-sweet parmap is needed in a 
## function or method and you do not want to require parmap(per).py
## 
## It is basically *just* for reference
################################################################################
################################################################################


# def simple_parmap(fun,seq,N=None,daemon=True):
#     """
#     Simple, bare-bones parallel map function similar to parmap
#     (or parmapper [1]) except much, much simpler. It lacks all 
#     bells and whistles but *does* perform parallel mapping
#     
#     Note: This always returns a list and not an iterator!
#           And will not return until all computation is complete
#     
#     Use parmap if it is availible. 
#     
#     Inspired by [2]
#     
#     [1]:https://github.com/Jwink3101/parmapper
#     [2]:https://stackoverflow.com/a/16071616/3633154
#     """
#     import multiprocessing as mp
#     import sys
#     if sys.platform.startswith('darwin') and \
#        sys.version_info >= (3,8) and \
#        mp.get_start_method(allow_none=True) != 'fork':
#         raise RuntimeError("Must set multiprocessing start_method to 'fork'")
#     if N is None:
#         N = mp.cpu_count()
#     def _fun(fun, q_in, q_out):
#         while True:
#             i, x = q_in.get()
#             if i is None:
#                 q_in.task_done()
#                 break
#             q_out.put((i, fun(x)))
#             q_in.task_done()
#     
#     q_in,q_out = mp.JoinableQueue(),mp.Queue()
#     
#     proc = [mp.Process(target=_fun, args=(fun, q_in, q_out)) for _ in range(N)]
#     for p in proc: 
#         p.daemon=daemon
#         p.start()
#     
#     count = 0
#     for ii,x in enumerate(seq):
#         q_in.put((ii,x))
#         count += 1 
#     
#     for _ in range(N): q_in.put((None,None))
#     res = [q_out.get() for _ in range(count)]
#     
#     q_in.join()
#     for p in proc: p.join()
# 
#     return [x for i, x in sorted(res)]


