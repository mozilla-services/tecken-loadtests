Ability to bombard [Mozilla Symbol Server](https://github.com/mozilla-services/tecken)'s
Symbolication service with tonnes of stacks as stored in `.json` files
and the Download service with tonnes of symbol URL requests.


## To Use (for Downloads)

1. Download or clone this repo.

2. Run a Python that has
[`requests`](http://requests.readthedocs.io/en/master/) installed.

3. Type something like `python download.py http://localhost:8000 symbol-queries-groups.csv`
assuming you have the download server running at `localhost:8000`

4. Sit and watch it or kill it with `Ctrl-C`. If you kill it before it
finishes (finishing is likely to take hours) stats are printed out with
what's been accomplished so far.

**Alternatively** you can do the same but add another CSV file that contains
looks for `code_file` and `code_id`. For example:

```
python download.py http://localhost:8000 downloading/symbol-queries-groups.csv downloading/socorro-missing.csv
```

That second file is expected to have the following header:
```
debug_file,debug_id,code_file,code_id
```

## How To Interpret The Results (for Downloads)

The results look like this after running for a while:

```
JOBS DONE SO FAR     256
RAN FOR              146.663s
AVERAGE RATE         1.75 requests/s

STATUS CODE               COUNT          MEDIAN         AVERAGE         % RIGHT
404                         238          0.540s          0.564s           97.90
302                          18          0.541s          0.558s          100.00
```

That means that 238 URLs were sent in. In 97.9% of the cases, tecken also
found that the symbol file didn't exist (compared with what was the case
when the csv file was made).
And there were 18 requests where the symbol existed and was able to
redirect to an absolute S3 URL.


## To Use (for Symbolication)

1. Download or clone this repo.

2. Run a Python that has
[`requests`](http://requests.readthedocs.io/en/master/) installed.

3. Type something like `python symbolicate.py stacks http://localhost:8000`
assuming you have the symbolication server running at `localhost:8000`

4. Sit and watch it or kill it with `Ctrl-C`. If you kill it before it
finishes (finishing is likely to take hours) stats are printed out with
what's been accomplished so far.


## How To Interpret The Results (for Symbolication)

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


## How the `symbol-queries-groups.csv` file was made

First of all, you need to enable logging on the
`org.mozilla.crash-stats.symbols-public` and
`org.mozilla.crash-stats.symbols-private` S3 buckets. Make the logging
go to the bucket `peterbe-symbols-playground-deleteme-in-2018` and for
each make the prefix be `public-symbols/` and `private-symbols/`
respectively.

The file `symbol-queries-groups.csv` was created by running
`generate-csv-logs.py` a bunch of ways:

1. `AWS_ACCESS_KEY=... AWS_SECRET_ACCESS_KEY=... python generate-csv-logs.py download`

2. `python generate-csv-logs.py summorize`

3. `python generate-csv-logs.py group`


## Molotov Testing

To start a [molotov testing](https://molotov.readthedocs.io/) there's a
`loadtest.py` script. Basic usage:

    molotov --max-runs 10 -cx loadtest.py

By default the base URL for this will be `http://localhost:8000`. If you
want to override that, change the environment variable `URL_SERVER`.
For example:

    URL_SERVER=https://symbols.dev.mozaws.net molotov --max-runs 10 -cx loadtest.py


## Make Symbol Zips

To load test Tecken with realistic `.zip` uploads, you can simulate the
uploads sent to Socorro in the past.

The `make-symbol-zip.py` script will look at the logs, pick a
recent one (uploaded by Mozilla RelEng)
and then download each and every file from S3 and make a `.zip` file in
your temp directory (e.g. `/tmp/massive-symbol-zips/symbols-2017-06-09T04_01_45.zip`).

Simply run it like this::

    python make-symbol-zip.py

In the stdout, it should say where it was saved.

Now you can use that to upload. For example:

    curl -X POST -H "Auth-Token: YYYYYYY" --form myfile.zip=@/tmp/massive-symbol-zips/symbols-2017-06-09T04_01_45.zip http://localhost:8000/upload/


## Test Symbol Upload

First you have to make a bunch of `.zip` files. See the section above on
"Make Symbol Zips". That script uses the same default save directory
as `upload-symbol-zips.py`. This script picks random `.zip` files from
that directory where they're temporarily saved. This script will actually
go ahead and make the upload.

First try:

    python upload-symbol-zips.py --help

By default, it will upload 1 random `.zip` file to
`http://localhost:8000/upload`. All the uploads are synchronous.

This does require an ``Auth-Token`` (aka. "API token") in the environment
called `AUTH_TOKEN`. Either export it or use like this:

    AUTH_TOKEN=7e353c4f34644ef6ba1cfb02b3c3662d python upload-symbol-zips.py

If you do the testing using `localhost:8000` but actually depend on uploading
the to an S3 bucket that is on the Internet, the uploads can become really
slow. Especially on a home broad band. To limit it to `.zip` files that
aren't too large you can add `--max-size` option. E.g.

    python upload-symbol-zips.py --max-size 100m

That will pick (randomly) only from `.zip` files that are 100Mb or less.
