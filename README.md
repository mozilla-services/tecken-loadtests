Ability to bombard [Mozilla Symbol Server](https://github.com/mozilla/tecken)'s
Symbolication service with tonnes of stacks as stored in `.json` files.

## To Use

1. Download or clone this repo.

2. Run a Python that has
[`requests`](http://requests.readthedocs.io/en/master/) installed.

3. Type something like `python main.py stacks http://localhost:8000`
assuming you have the symbolcation server running at `localhost:8000`

4. Sit and watch it or kill it with `Ctrl-C`. If you kill it before it
finishes (finishing is likely to take hours) stats are printed out with
what's been accomplished so far.


## Hot To Interpret The Results

When you finish (or kill it unfinished) it will print out something
that looks like this:

```
TOTAL SO FAR 369 JOBS DONE
KEY                            SUM        AVG     MEDIAN    STD-DEV
cache_lookups.count           1083          2          3       1.73
cache_lookups.size           1.8GB      5.0MB       0.0B      8.7MB
cache_lookups.time          8.505s     0.023s     0.001s     0.038s
downloads.count                941          2          2       1.73
downloads.size              23.9GB     66.3MB     76.5MB     40.4MB
downloads.time           3179.728s     8.594s    10.257s     4.432s
loader_time              3350.723s     9.056s    10.758s      4.484s
modules.count                 1083          2          3       1.73
stacks.count                  8497         22         25       5.00
stacks.real                   8334         22         25       5.39
time                     3351.656s     9.059s    10.725s      4.443s


IN CONCLUSION...
Final Download Speed    7.7MB/s
Final Cache Speed       219.0MB/s
```

Here's the same output but annotated with comments:


```
TOTAL SO FAR 369 JOBS DONE
KEY                            SUM        AVG     MEDIAN    STD-DEV

# How many times we've tried to look up a module in the LRU cache.
cache_lookups.count           1083          2          3       1.73

# How much data we have successfully extracted out of the LRU cache.
cache_lookups.size           1.8GB      5.0MB       0.0B      8.7MB

# The time spent doing lookups on the LRU cache (hits or misses).
cache_lookups.time          8.505s     0.023s     0.001s     0.038s

# How many distinct URLs that have had to be downloaded.
downloads.count                941          2          2       1.73

# The amount of data that has been downloaded from URLs (uncompressed).
downloads.size              23.9GB     66.3MB     76.5MB     40.4MB

# The time spent doing URL downloads.
downloads.time           3179.728s     8.594s    10.257s     4.432s

# A special one. This wraps the 'downloads.time' plus the time it
# takes to make the and getting the response. Should be marginally
# bigger than than 'downloads.time'
loader_time              3350.723s     9.056s    10.758s      4.484s

# Distinct number of modules that have been come across. Note
# that this number is the same as 'cache_lookups.count' above.
modules.count                 1083          2          3       1.73

# Total number of individual stacks symbolicated.
stacks.count                  8497         22         25       5.00

# Same as 'stacks.count' except sometimes the module index is -1 so we
# know we don't have to symbolicate it and can just insert its hex offset
# directly.
stacks.real                   8334         22         25       5.39

# Total time spent symbolicating all stacks. This spans cache misses and
# cache hits.
time                     3351.656s     9.059s    10.725s      4.443s


IN CONCLUSION...

# The download speed doing downloads. But note! this is UNcompressed so it's
# likely to be much higher (how much? roughly the average gzip size of a
# symbol text file) than what you get for your broadband when you open
# http://fast.com.
Final Download Speed    7.7MB/s

# The speed at which the web service can extract data out of the LRU cache.
# This is a really important number if you want to optimize how the LRU
# data pipelining works.
Final Cache Speed       219.0MB/s
```


## Word Of Warning

This script picks sample JSON stacks to send in randomly. Every time.
That means that if you start it, kill it and start again, it's unlikely
that you'll be able to benefit much from the cache of the first run.
