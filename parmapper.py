#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

__version__ = '20181101'

import multiprocessing as mp
import multiprocessing.dummy as mpd
from threading import Thread
import threading
import sys
from collections import defaultdict

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

def parmap(fun,seq,N=None,Nt=1,chunksize=1,ordered=True,\
                daemon=False,progress=False,
                args=(),kwargs=None,
                star=False,kwstar=False):
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

    sequence
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
        Will be (re)set to max(chunksize,Nt)

    ordered [True] (bool)
        Whether or not to order the results. If False, will return in whatever
        order they finished.

    daemon [False] (bool)
        Sets the multiprocessing `daemon` flag. If  True, can not spawn child
        processes (i.e. cannot nest parmap) but should allow for CTRL+C type
        stopping. Supposedly, there may be issues with CTRL+C with it set to
        False. Use at your own risk

    progress [False] (bool)
        Display a progress bar or counter.
        Warning: Inconsistant in iPython/Jupyter notebooks and may clear
        other printed content. Instead, specify as 'nb' to use a Jupyter 
        Widget progress bar.
    
    args [tuple()]
        Specify additional arguments for the function
    
    kwargs [dict()]
        Specify additional keyword arguments

    star [False]
        If True, the arguments to the function will be "starred" so, for example
        if `seq = [ (1,2), (3,4) ]`, the function will be called as
            star == True
                fun((1,2))
            star == False
                fun(1,2) <==> fun(*(1,2))
        
    kwstar [False]
        Assumes all items are (seqargs,seqkwargs) where `args` RESPECTS `star` 
        setting and still includes `args` and `kwargs`. See 
        "Additional Arguments" below.
        

    Additional Arguments
    --------------------
    As noted above, there are many ways to pass additional arguments to
    your function. All of these are not completely needed since parmap
    makes using lambdas so easy, but they are there if preffered.
    
    Assume the following function:
    
        def dj(dictA,dictB):
            dictA = dictA.copy()
            dictA.update(dictB) # NOTE: dictB takes precedence
            return dictA

    Then the behavior is as follows where `args` and `kwargs` come from
    they main function call. `args` and `kwargs` are those set in the
    function call. `val` (singular), `vals` (sequance of values) and `kwvals`
    are set per iterated.
    
    | star  | kwstar | expected item | function args  | function keywords   |
    |-------|--------|---------------|----------------|---------------------|
    | False | False  | val           | *((val,)+args) | **kwargs            |
    | True  | False  | vals          | *(vals+args)   | **kwargs            |
    | False | True   | val,kwval     | *((val,)+args) | **dj(kwargs,kwvals) |+
    | True  | True   | vals,kwval    | *(vals+args)   | **dj(kwargs,kwvals) |+
                                                        
                + Note the ordering so kwvals takes precedance

    Note:
    ------
    Performs SEMI-lazy iteration based on chunksize. It will exhaust the input
    iterator but will yield as results are computed (This is similar to the
    `multiprocessing.Pool().imap` behavior)

    Explicitly wrap the parmap call in a list(...) to force immediate
    evaluation

    Threads and/or processes:
    -------------------------
    This tool has the ability to split work amongst python processes
    (via multiprocessing) and python threads (via the multiprocessing.dummy
    module). Python is not very performant in multi-threaded situations
    (due to the GIL) therefore, processes are the usually the best for CPU
    bound tasks and threading is good for those that release the GIL (such
    as IO-bound tasks). 
    
    WARNING: many NumPy functions *do* release the GIL and can be threaded, 
             but many NumPy functions are, themselves, multi-threaded.

    Alternatives:
    -------------

    This tool allows more data types, can split with threads, has an optional
    progress bar, and has fewer pickling issues, but these come at a small cost. 
    For simple needs, the following may be better:

    >>> import multiprocessing as mp
    >>> pool = mp.Pool(N) # Or mp.Pool() for N=None
    >>> results = list( pool.imap(fun,seq) ) # or just pool.map
    >>> pool.close()
    
    Additional Note
    ---------------
    For the sake of convienance, a `map=imap=__call__` and
    `close = lamba *a,**k:None` are also added so a parmap function can mimic
    a multiprocessing pool.

    Last Updated:
    -------------
    2018-11-01
    """
    
    # Build up a dummy function with args,vals,kwargs, and kwvals
    if kwargs is None:
        kwargs = {}
    
    def _fun(ss):
        if kwstar:
            _args,_kwargs = ss # Will raise a ValueError if too many args. User error!
        else:
            _args = ss
            _kwargs = {}
        if star:
            _args = _args + args
        else:
            _args = ((_args,) + args)
        kw = kwargs.copy() # from function call
        kw.update(_kwargs)
        return fun(*_args,**kw)
            
    N = CPU_COUNT if N is None else N
    chunksize = max(chunksize,Nt)

    try:
        tot = len(seq)
    except TypeError:
        tot = None

    # Build a counter iterator based on settings and tqdm
    if tqdm is None:
        if   isinstance(progress,(str,unicode))\
         and progress.lower() in ['jupyter','notebook','nb']:
            counter = partial(_counter_nb,tot=tot)
        else:
            counter = partial(_counter,tot=tot)
    else:
        if   isinstance(progress,(str,unicode))\
         and progress.lower() in ['jupyter','notebook','nb']\
         and hasattr(tqdm,'tqdm_notebook'):
            counter = partial(tqdm.tqdm_notebook,total=tot)
        else:
            counter = partial(tqdm.tqdm,total=tot) # Set the total since tqdm won't be able to get it.
    
    # Handle N=1 without any multiprocessing
    if N == 1:
        if Nt == 1:
            out = imap(_fun,seq)
        else:
            pool = mpd.Pool(Nt)      # thread pools don't have the pickle issues
            out = pool.imap(_fun,seq)

        if progress:
           out = counter(out)
        for item in out:
            yield item

        if Nt > 1:
            pool.close()
        return
    
    q_in = mp.JoinableQueue() # Will need to `join` later to make sure is empty
    q_out = mp.Queue()

    # Start the workers
    workers = []
    for _ in range(N):
        worker = mp.Process(target=_worker, args=(_fun, q_in, q_out,Nt))
        worker.daemon = daemon
        worker.start()
        workers.append(worker)

    # Create a separate thread to add to the queue in the background
    def add_to_queue():
        for iixs in _iter_chunks(enumerate(seq),chunksize):
            q_in.put(iixs)

        # Once (if ever) it is exhausted, send None to close workers
        for _ in xrange(N):
            q_in.put(None)

    add_to_queue_thread = Thread(target=add_to_queue)
    add_to_queue_thread.start()

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
            yield out

    # Chain generators on output
    out = queue_getter()
    if progress:
        out = counter(out)

    if ordered:
        out = _sort_generator_unique_integers(out,key=lambda a:a[0])

    # Return items
    for item in out:
        yield item[1]
    
    # Clean up
    q_in.join() # Make sure there is nothing left in the queue
    for worker in workers:
        worker.join() # shut it down
    

# Add dummy methods
parmap.map = parmap.imap = parmap.__call__
parmap.close = lambda *a,**k:None

def _counter(items,tot=None):
    for ii,item in enumerate(items):
        if tot is not None:
            _txtbar(ii,tot,ticks=50,text='')
        else:
            txt = '{}'.format(ii+1)
            print('\r%s' % txt,end='')
            sys.stdout.flush()
        yield item

def _counter_nb(items,tot=None):
    from ipywidgets import IntProgress,IntText
    from IPython.display import display
    
    if tot is not None:
        g = IntText(value=0,description='total = %d' % tot)
    
        f = IntProgress(min=0,max=tot)
        display(f)
        g.desription='hi'

    else:
        g = IntText(value=0)
        f = None

    display(g)
    for ii,item in enumerate(items):
        if f:
            f.value += 1 
        g.value+=1
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
#         for ix in iixs:
        def _ap(ix):
            i,x = ix
            q_out.put((i, fun(x)))
        list(_map(_ap,iixs)) # list forces the iteration
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
    print('\r%s' % txt,end='')
    sys.stdout.flush()

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
