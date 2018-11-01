# parmapper

`parmapper` is a simple, easy-to-use, robust way to perform parallel computations with python. It is designed with simplicity and robustness before absolute performance.

When to use `parmapper`: (*roughly* in order)

* non-pickleable functions such as `lambda` and in some classes
* common interface to threads and/or proceses
* Ability to specify additional arguments and keywords without `partial` or wrappers (though, since you can parallelize `lambda`, this isn't critical)
* Ability to pass a sequence of keywords (see `kwstar` mode). 
* no desire for boilerplate code or management of processes and pools
* integration with tools such as progress bars

When **not** to use `parmapper`:

* absolute performance is key! (`parmapper` has a *slight* overhead but it is minimal)
* Many successive calls to a `map` that would benefit from a common pool (`parmapper` creates and destroys its pool on each call)
* Desire for advanced parallel topologies

Tested with python 2.7 and 3.3+

## Install

Install directly from github:

    pip install git+https://github.com/Jwink3101/parmapper

## Usage

`parmapper` can be used anywhere you would use a regular `imap` or `map` function or a `multiprocessing.Pool().map` (or `imap`, or `starmap`, etc). Note that `parmapper` performs *semi*-lazy evaluation. The input sequence is evaluated but results are cached until the `parmapper` is iterated. This is the same behavior as `multiprocess.Pool().imap`.

Consider a simple function:

```python
def do_something(item):
    result = ...# Do something time consuming
    return result

results = list(parmapper.parmapper(do_something,items))
```

You can replace a simple loop as follows:

```python
# Serial -- for loop
results = []
for item in items:
    result = ...# Do something time consuming
    results.append(result)
    
# Serial -- function
def proc(item):
    result = ...# Do something time consuming
    return result
results = list(map(proc,items))

# Parallel
results = list(parmapper.parmap(proc,items))
```

The functions can still use variables in scope but they are, for all intents and purposes, read-only. You can only modify them on the


## star and kwstar

When `star=True` and `kwstar=False`, this mimicks `map.starmap` where the arguments are passed as `*vals`. This tool also adds `kwstar` mode where it is assumed that each input is a tuple of `(arg,kwarg)` where `arg` respects the `star` settings.

Note that this is *in addition* to a *fixed* `args` and `kwargs` keyword.

In this let
```python
def dj(dictA,dictB):
    dictA = dictA.copy()
    dictA.update(dictB) # dictB takes precedence
    return dictA
```

| star  | kwstar | expected item | function `*args` | function `**kwargs`   |
|-------|--------|---------------|------------------|-----------------------|
| False | False  | `val`         | `*((val,)+args)` | `**kwargs`            |
| True  | False  | `vals`        | `*(vals+args)`   | `**kwargs`            |
| False | True   | `val,kwval`   | `*((val,)+args)` | `**dj(kwargs,kwvals)` |
| True  | True   | `vals,kwval`  | `*(vals+args)`   | `**dj(kwargs,kwvals)` |

Consider the following:

Multiple arguments with `star=True`

```python
def do_something(itemA,itemB):
    result = ...# Do something time consuming
    return result

results = list(parmapper.parmap(do_something,zip(itemsA,itemsB),star=True))
```

Or *changing* keyword arguments

```python
def do_something(item,opt=False):
    result = ...# Do something time consuming
    return result

results = list(parmapper.parmap(do_something,
                             zip(items,[{'opt':(i%2==0)} for i in range(10)]),
                             kwstar=True))
```

Or, both changing keyword arguments *and* multiple arguments. Note that you must just pass a length 2 tuple of `(*args,kwargs)`

```python
def do_something(itemA,itemB,opt=False):
    result = ...# Do something time consuming
    return result

itemsAB = zip(itemsA,itemsB)
kws = [{'opt':(i%2==0)} for i in range(10)]


results = list(parmapper.parmap(do_something,zip(itemsAB,kws),
                             star=True,kwstar=True))
```

And, finally, let's say you have a fixed argument and fixed keyword:

```python
def do_something(itemA,itemB,itemC,opt=False,opt2=True):
    result = ...# Do something time consuming
    return result

itemsAB = zip(itemsA,itemsB)
kws = [{'opt':(i%2==0)} for i in range(10)]

results = list(parmapper.parmap(do_something,zip(itemsAB,kws),
                             star=True,kwstar=True,
                             args=(itemC,),kwargs={'opt2':False}))
```

## Tips

### Progress Bars

Included in the code are very rough progress bars. However, if you have `tqdm` installed, it will use that for prettier formatting.

### Concurrency + Parallel

When processing data, it is often convenient to have concurrency and parallelism together (concurrency `!=` parallel). This can be done with a series of generator expressions. Consider the following:

```python
try:
    from itertools import imap # python 2
except ImportError:
    imap = map

from parmapper import parmap

data = data_load_generator() 
data = imap(preprocess,data)
data = parmap(expensive_computation,data)
data = imap(postprocess,data)

# Execute the analysis chain
data = list(data)
```

In this example `data` is processed as it is generated with the expensive part done in parallel.

## Technical Details

This code uses iterators/generators to handle and distribute the workload. By doing this, it is easy to have all results pass through a common counting function for display of the progress without the use of global (multiprocessing manager) variables and locks.

With the exception of when N == 1 (where it falls back to serial methods) the code works as follows:

- A background thread is started that will iterate over the incoming sequence and add items to the queue. If the incoming sequence is exhausted, the worker sends kill signals into the queue. The items are also chunked and enumerated (used later to sort). 
- After the background thread is started a function to pull from the OUTPUT queue is created. This counts the number of closed processes but otherwise yields the computed result items 
- A pool of workers is created. Each worker will read from the input queue and distribute the work amongst threads (if using). It will then return the resuts into a queue 
- Now the main work happens. It is done as chain of generators/iterators. The background worker has already begin adding items to the queue so now we work through the output queue. Note that this is in serial since the work was already done in parallel 
- Generator to pull from the result queue 
- Generator to count and display progress (if progress=True). 
- Generator to hold on to and return items in a sorted manner if sorting is requested. This can cause itermediate results to be stored until they can be returned in order 
- The output generator chain is iterated pulling items through and then are yielded. 
- cleanup and close processes (if/when the input is exhausted)

## Aside: Name Change

I originally named the module `parmap.py` but it has been used before so I changed the top-level module to `parmapper.py` and the function is still `parmap` (with `parmapper=parmap` as a fallback). I *think* I corrected everything but I may have missed a few places
