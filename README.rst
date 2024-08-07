================
Tecken loadtests
================

Set of tools for load testing Mozilla Symbols Service and Mozilla Symbolication
Service.


Setup
=====

1. Clone the repo.
2. Run ``make build`` to build the Docker container.


Testing Eliot
=============

Getting stack data
------------------

You'll need stack data to test symbolication.

To build stacks::

    $ make buildstacks


Testing Symbolication API
-------------------------

1. Run::

       $ make shell
       app@...:/app$ python bin/symbolication.py stacks https://HOST/

   to run it against HOST.

2. Sit and watch it or kill it with ``Ctrl-C``. If you kill it before it
   finishes stats are printed out with what's been accomplished so far.


The results look like this:

::

    TOTAL 729 JOBS DONE
     Key             |         Sum |       Avg |       50% |          StdDev
    -----------------|-------------|-----------|-----------|-----------------
     cache.count     |   3,503.000 |           |           |
     cache.hits      |   2,598.000 |           |           |
     cache.time      |   671.088 s |   0.922 s |   0.471 s |           0.845
     downloads.count |     905.000 |           |           |
     downloads.size  |   103.19 gb | 331.24 mb | 519.14 mb | 316,107,251.274
     downloads.time  |   937.658 s |   2.939 s |   3.673 s |           2.352
     time            | 5,727.419 s |   7.857 s |   2.173 s |          11.289


    In conclusion...
    Final Average Download Speed:    112.69 mb/s
    Total time NOT downloading or querying cache:    4,118.673 s
    Average time NOT downloading or querying cache:  5.650 s


Here's the same output but annotated with comments:

::

    TOTAL 729 JOBS DONE
     Key             |         Sum |       Avg |       50% |          StdDev
    -----------------|-------------|-----------|-----------|-----------------

    # How many times we've tried to look up a module in the LRU cache.
     cache.count     |   3,503.000 |           |           |

    # How many times it was a cache hit.
     cache.hits      |   2,598.000 |           |           |

    # The time spent doing lookups on the LRU cache.
     cache.time      |   671.088 s |   0.922 s |   0.471 s |           0.845

    # How many distinct URLs that have had to be downloaded.
     downloads.count |     905.000 |           |           |

    # The amount of data that has been downloaded from URLs (uncompressed).
     downloads.size  |   103.19 gb | 331.24 mb | 519.14 mb | 316,107,251.274

    # The time spent doing URL downloads.
     downloads.time  |   937.658 s |   2.939 s |   3.673 s |           2.352

    # Total time spent on symbolication
     time            | 5,727.419 s |   7.857 s |   2.173 s |          11.289


    In conclusion...

    # The download speed doing downloads. But note! this is UNcompressed so it's
    # likely to be much higher (how much? roughly the average gzip size of a
    # symbol text file) than what you get for your broadband when you open
    # http://fast.com.
    Final Average Download Speed:    112.69 mb/s

    # This is the total time spent doing neither downloading nor querying the
    # cache. So this is roughly the time it takes to parse symbols files and
    # perform the symbolication.
    Total time NOT downloading or querying cache:    4,118.673 s

    # This is the total time spent doing neither downloading nor querying
    # divided by number of requests.
    Average time NOT downloading or querying cache:  5.650 s


.. Note::

   This script picks sample JSON stacks to send in randomly. Every time.
   That means that if you start it, kill it and start again, it's unlikely
   that you'll be able to benefit much from the cache of the first run.


Load testing with Locust
------------------------

To test with Locust, use the scripts in ``locust-eliot`` directory. See that
README.rst for details.

For example::

   $ make shell
   app@...:/app$ cd locust-eliot
   app@...:/app/locust-eliot$ locust_eliot.sh aws-stage


Testing Tecken
==============

Testing the download API
------------------------

1. Run::

       $ make shell
       app@...:/app$ python bin/download.py HOST downloading/symbol-queries-groups.csv

   to run it against HOST.

2. Sit and watch it or kill it with ``Ctrl-C``. If you kill it before it
   finishes stats are printed out with what's been accomplished so far.

**Alternatively** you can do the same but add another CSV file that
contains looks for ``code_file`` and ``code_id``. For example:

::

   $ make shell
   app@...:/app$ python download.py HOST downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

That second file is expected to have the following header:

::

   debug_file,debug_id,code_file,code_id


The results look like this:

::

   JOBS DONE SO FAR     302
   RAN FOR              173.957s
   AVERAGE RATE         1.74 requests/s

   STATUS CODE           COUNT        MEDIAN    (INTERNAL)       AVERAGE    (INTERNAL)       % RIGHT
   404                     274        0.644s        0.651s        0.564s        0.660s         95.62
   302                      28        0.657s        0.639s        0.693s        0.663s        100.00

That means that 302 URLs were sent in. In 95.62% of the cases, Tecken also
found that the symbol file didn't exist (compared with what was the case when
the CSV file was made). And there were 28 requests where the symbol existed and
was able to redirect to an absolute url for the symbol file.

The ``(INTERNAL)`` is the median and average of the seconds it took the
*server*, internally, to make the lookup. So if a look up took 0.6 seconds and
0.5 seconds internally, it means there was an 0.1 second overhead of making the
request to Tecken. In that case, the 0.5 is basically purely the time it takes
Tecken to talk to the storage server. One thing to note is that Tecken can
iterate over a list of storage servers so this number covers lookups across all
of them.


Make Symbol Zips
----------------

To load test Tecken with realistic ``.zip`` uploads, you can simulate
the uploads sent to Tecken in the past.

The ``make-symbol-zip.py`` script will look at the logs, pick a recent
one (uploaded by Mozilla RelEng) and then download each and every file
from S3 and make a ``.zip`` file in ``upload-zips`` directory.

Simply run it like this::

   $ make shell
   app@...:/app$ python bin/make-symbol-zip.py

In the stdout, it should say where it was saved.

Now you can use that to upload. For example:

::

   curl -X POST -H "Auth-Token: YYYYYYY" \
       --form myfile.zip=@/tmp/massive-symbol-zips/symbols-2017-06-09T04_01_45.zip \
       http://localhost:8000/upload/


Testing upload API
------------------

Builds are made on TaskCluster, as an artifact it builds symbols zip files. To
get a list of recent ones of these for local development or load testing run
the script:

::

   $ make shell
   app@...:/app$ python bin/list-firefox-symbols-zips.py

Each URL can be used to test symbol upload by URL. Uses the same default
save directory as ``upload-symbol-zips.py``.

This script picks random ``.zip`` files from that directory where they're
temporarily saved. This script will actually go ahead and make the upload.

Run::

    $ make shell
    app@...:/app$ python bin/upload-symbol-zips.py

By default, it will upload 1 random ``.zip`` file to
``http://localhost:8000/upload``. All the uploads are synchronous.

This does require an ``Auth-Token`` (aka. "API token") in the
environment called ``AUTH_TOKEN``. Either export it or use like this:

::

    $ make shell
    app@...:/app$ AUTH_TOKEN=7e353c4f34644ef6ba1cfb02b3c3662d python bin/upload-symbol-zips.py

If you do the testing using ``localhost:8000`` but actually depend on
uploading the to an S3 bucket that is on the Internet, the uploads can
become really slow. Especially on a home broad band. To limit it to
``.zip`` files that aren't too large you can add ``--max-size`` option.
E.g.

::

    $ make shell
    app@...:/app$ python bin/upload-symbol-zips.py --max-size 100m

That will pick (randomly) only from ``.zip`` files that are 100Mb or
less.


Generating ``symbols-uploaded/YYYY-MM-DD.json.gz``
--------------------------------------------------

Get an API token from
`Crash-stats <https://crash-stats.mozilla.com/api/tokens/>`__ with the
``View all Symbol Uploads`` permission. Then run:

::

    $ make shell
    app@...:/app$ AUTH_TOKEN=bdf6effac894491a8ebd0d1b15f3ab5a python bin/generate-symbols-uploaded.py


Analyzing Symbol Uploads
------------------------

There's a script called ``analyze-symbol-uploads-times.py`` which gives
insight into symbol upload times. Use it to analyze how concurrent
uploads work/optimize. You need an auth token with the "View All Symbols
Uploads" permission. Then run:

::

    $ make shell
    app@...:/app$ AUTH_TOKEN=66...92e python bin/analyze-symbol-uploads-times.py --domain=symbols.stage.mozaws.net --limit=10


Uploading by Download URL from TaskCluster
------------------------------------------

If you run ``python list-firefox-symbols-zips.py 3`` it will find 3
recent symbols builds URLs on TaskCluster. You can actually pipe them
into the the ``upload-symbol-zips.py`` script. For example, this is how
you do it for stage:

::

   $ make shell
   app@...:/app$ export AUTH_TOKEN=xxxxxxxStageAPITokenxxxxxxxxx
   app@...:/app$ python bin/list-firefox-symbols-zips.py 1 | python bin/upload-symbol-zips.py https://symbols.stage.mozaws.net --download-urls-from-stdin --max-size=2gb
