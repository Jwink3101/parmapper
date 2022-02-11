# parmapper

`parmapper` is a simple, easy-to-use, robust way to perform parallel computations with python. It is designed with simplicity and robustness before absolute performance.

When to use `parmapper`: (*roughly* in order)

* Simple and easy with minimal code (no boilerplate) is preferred.
* non-pickleable functions such as `lambda` and in some classes
* common interface to threads and/or processes
* Ability to specify additional arguments and keywords without `partial` or wrappers. (see `args`)
* Ability to pass a sequence of keywords (see `kwstar` mode) and/or arguments (see `star` mode). 
* Integration with tools such as progress bars

When **not** to use `parmapper`:

* You use Windows or another platform that doesn't support `fork` mode.
    * See below for notes on macOS
    * Works on Linux
* Absolute performance is key! (`parmapper` has a *slight* overhead but it is minimal)
* Many successive calls to a `map` that would benefit from a common pool (`parmapper` creates and destroys its pool on each call)
* Desire for advanced parallel topologies

Tested with python 2.7 and 3.3+ (see note about macOS and 3.8+)

## Install

Install directly from github:

    python -m pip install git+https://github.com/Jwink3101/parmapper

## Usage

`parmapper` can be used anywhere you would use a regular `imap` (or `map`), a `multiprocessing.Pool().map` (or `imap`, or `starmap`, etc), or `concurrent.futures.ProcessPoolExecutor` (or `ThreadPoolExecutor`). Note that `parmapper` performs *semi*-lazy evaluation. The input sequence is evaluated but results are cached until the `parmapper` is iterated. This is the same behavior as `multiprocess.Pool().imap`.

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

## star and kwstar

As noted above, there are many ways to pass additional arguments to your function. All of these are not completely needed since parmap makes using lambdas so easy, but they are there if preffered.

Assume the following function:

```python
def dj(dictA,dictB):
    '''Join dictA and dictB where dictB takes precedence'''
    dictA = dictA.copy()
    dictA.update(dictB) # NOTE: dictB takes precedence
    return dictA
```

Then the behavior is as follows where `args` and `kwargs` come from they main function call. The `val` (singular), `vals` (sequence/tuple of  values), and `kwvals` are set via the sequence.

| star  | kwstar | expected item | function args  | function keywords    |
|-------|--------|---------------|----------------|----------------------|
| False | False  | val           | *((val,)+args) | **kwargs            †|
| True  | False  | vals          | *(vals+args)   | **kwargs             |
| None  | False  | ---           | *args          | **kwargs            °|
| None  | True   | ---           | *args          | **dj(kwargs,kwvals) ‡|
| False | True   | val,kwval     | *((val,)+args) | **dj(kwargs,kwvals) ‡|
| True  | True   | vals,kwval    | *(vals+args)   | **dj(kwargs,kwvals) ‡|                                                     

* † Default
* ° If kwargs and args are empty, basically calls with nothing
* ‡ Note the ordering so kwvals takes precedance


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

## macOS and Python 3.8

This tool relies on and assumes `multiprocessing` will use `fork` to create new processes. This is why it is not compatible with Windows. 

However, according to the [Python 3.8 documentation][py3.8]:

> *Changed in version 3.8:* On macOS, the spawn start method is now the default. The fork start method should be considered unsafe as it can lead to crashes of the subprocess. [See bpo-33725](https://bugs.python.org/issue33725).

[py3.8]:https://docs.python.org/3.8/library/multiprocessing.html#contexts-and-start-methods

As such, the start method must be explicitly set when Python loads:

```python
import multiprocessing as mp
mp.set_start_method('fork')
```

Or, call 

```python
import parmapper as parmap
parmap.set_start_method()
```

Or, set `PYTOOLBOX_SET_START=true` environment variable and it will be set as needed upon import. To do this all the time, put the following in your `.bashrc`:

```bash
export PYTOOLBOX_SET_START=true
```

It is also good to set the following environment variable. Note that this must be set *before* Python starts. (sources: [\[1\]](https://www.wefearchange.org/2018/11/forkmacos.rst.html), \[[2\]](https://stackoverflow.com/q/50168647/3633154) ):

```bash
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
```

Future Python versions may change the defaults further and will have to be considered as they are released.

Note that nothing has *actually* changed making it more or less "safe" to use this method. It is something that has been discovered. While it has worked in practice, use at your own risk.

## Additional Tools

`parmapper` also comes with `ReturnProcess` and `ParEval`.

### `ReturnProcess`

This is a simple function to let you call different functions in the background and wait for them to finished. It is basically a `multiprocessing.Process` object that returns the result on `join()`.

Replace: 
```python
res1 = slow(arg1,kw=arg2)
res2 = slower(arg3,kw=arg4)
```
with:
```python
p1 = ReturnProcess(slow,args=(arg1,),kwargs={'kw':arg2}).start()
p2 = ReturnProcess(slower,args=(arg3,),kwargs={'kw':arg4}).start()
res1,res2 = p1.join() , p2.join()
```
### `ParEval`

This tool is aimed solely at NumPy functions that have the signature `fun(X)` where `X` is (N,ndim). It will split `X` appropriately and join at the end.

Replace:
```python
results = fun(X)
```
with:
```python
parfun = ParEval(fun)
results = parfun(X)
```

Must have NumPy installed.

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
- Generator to hold on to and return items in a sorted manner if sorting is requested. This can cause intermediate results to be stored until they can be returned in order 
- The output generator chain is iterated pulling items through and then are yielded. 
- cleanup and close processes (if/when the input is exhausted)

## Aside: Name Change

I originally named the module `parmap.py` but it has been used before so I changed the top-level module to `parmapper.py` and the function is still `parmap` (with `parmapper=parmap` as a fallback). I *think* I corrected everything but I may have missed a few places
