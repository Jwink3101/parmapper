# Changelog

## `20220211.0`

- Added `ReturnThread`. Unrelated to parallel mapping but a useful tool to allow multiple functions to run at the same time.
- Fixed bug when number of items is smaller than chunksize
- Added `total` keyword to pre-specify the size of `seq` if it's known. (e.g. `itertools.combinations` does not know the size but you can compute it)
- tqdm fallback also prints to stderr
- Updated documenation