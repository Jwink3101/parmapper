# parmap

`parmap` is a simple, easy-to-use, robust way to perform parallel computations with python. It is designed with simplicity and robustness before absolute performance.

When to use `parmap`: (*roughly* in order)

* non-pickleable functions such as `lambda` and in some classes
* common interface to threads and/or proceses
* Ability to specify additional arguments and keywords without `partial` or wrappers (though, since you can parallelize `lambda`, this isn't critical)
* Ability to pass a sequence of keywords (see `kwstar` mode). 
* no desire for boilerplate code or management of processes and pools
* integration with tools such as progress bars

When **not** to use `parmap`:

* absolute performance is key! (`parmap` has a *slight* overhead but it is minimal)
* Many successive calls to a `map` that would benefit from a common pool (`parmap` creates and destroys its pool on each call)
* Desire for advanced parallel topologies

## Usage

`parmap` can be used anywhere you would use a regular `imap` or `map` function or a `multiprocessing.Pool().map` (or `imap`, or `starmap`, etc). Note that `parmap` performs *semi*-lazy evaluation. The input sequence is evaluated but results are cached until the `parmap` is iterated. This is the same behavior as `multiprocess.Pool().imap`.

Consider a simple function:

```python
def do_something(item):
    result = ...# Do something time consuming
    return result

results = list(parmap.parmap(do_something,items))
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
results = list(parmap(proc,items))
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

results = list(parmap.parmap(do_something,zip(itemsA,itemsB),star=True))
```

Or *changing* keyword arguments

```python
def do_something(item,opt=False):
    result = ...# Do something time consuming
    return result

results = list(parmap.parmap(do_something,
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


results = list(parmap.parmap(do_something,zip(itemsAB,kws),
                             star=True,kwstar=True))
```

And, finally, let's say you have a fixed argument and fixed keyword:

```python
def do_something(itemA,itemB,itemC,opt=False,opt2=True):
    result = ...# Do something time consuming
    return result

itemsAB = zip(itemsA,itemsB)
kws = [{'opt':(i%2==0)} for i in range(10)]

results = list(parmap.parmap(do_something,zip(itemsAB,kws),
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

from parmap import parmap

data = data_load_generator() 
data = imap(preprocess,data)
data = parmap(expensive_computation,data)
data = imap(postprocess,data)

# Execute the analysis chain
data = list(data)
```


