# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Downloads urls from a file in the form of::

    URI,STATUS CODE,PRIVATE,COUNT

and reports responses and timings.
"""

from collections import defaultdict
import csv
import os
import random
import statistics
import time
from urllib.parse import urljoin

import requests
from requests.exceptions import ConnectionError


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return '%3.1f%s%s' % (num, unit, suffix)
        num /= 1024.0
    return '%.1f%s%s' % (num, 'Yi', suffix)


def number_fmt(x):
    if isinstance(x, int):
        return str(x)
    return '{:.2f}'.format(x)


def time_fmt(x):
    if x == 'n/a':
        return x
    if x > 500:
        minutes = x // 60
        seconds = x % 60
        return '{}m{:.1f}s'.format(minutes, seconds)
    # elif x < 0.001:
    #     return '{:.2f}ms'.format(x * 1000)
    return '{:.3f}s'.format(x)


def wc_dir(path):
    return len(os.listdir(path))


def wc_file(path):
    with open(path) as fp:
        return fp.read().count('\n')


def listify(d):
    for key, value in d.items():
        if isinstance(value, dict):
            listify(value)
        else:
            d[key] = [value]


def appendify(source, dest):
    for key, value in source.items():
        if isinstance(value, dict):
            appendify(value, dest[key])
        else:
            dest[key].append(value)


def _stats(numbers):
    try:
        return (
            statistics.median(numbers),
            statistics.mean(numbers),
            statistics.stdev(numbers),
        )
    except statistics.StatisticsError:
        return (
            'n/a', 'n/a', 'n/a'
        )


def run(
    base_url,
    csv_file,
    socorro_missing_csv_file=None,
    only_microsoft_like_symbols=False,
):
    uris_count = wc_file(csv_file)
    print(format(uris_count, ','), 'LINES')
    print('\n')

    jobs_done = []

    cache_hits = []
    ignore_hits = 0

    code_files_and_ids = {}
    if socorro_missing_csv_file:
        with open(socorro_missing_csv_file) as f:
            reader = csv.reader(f)
            header = next(reader)
            _expect = ['debug_file', 'debug_id', 'code_file', 'code_id']
            assert header == _expect, header
            for row in reader:
                debug_file, debug_id, code_file, code_id = row
                code_files_and_ids[(debug_file, debug_id)] = (
                    code_file,
                    code_id,
                )

    def print_total_jobs_done(finished):
        print('\n')
        print(
            (finished and 'JOBS DONE' or 'JOBS DONE SO FAR').ljust(20),
            format(len(jobs_done), ',')
        )
        print(
            'IGNORE HITS'.ljust(20),
            ignore_hits,
            ' ({:.1f}%)'.format(
                100 * ignore_hits / len(jobs_done)
            )
        )

        total_duration = times[-1] - times[0]
        print('RAN FOR'.ljust(20), time_fmt(total_duration))
        print(
            'AVERAGE RATE'.ljust(20),
            number_fmt(len(jobs_done) / total_duration),
            'requests/s'
        )

        by_got_times = defaultdict(list)
        by_got_matched = defaultdict(list)
        for job in jobs_done:
            expect = job['expect']
            got = job['got']
            matched = (
                expect == got or
                (expect == 403 and got == 404) or
                (expect == 200 and got == 302)
            )

            by_got_matched[got].append(matched)
            by_got_times[got].append((job['time'], job['internal_time']))

        N = 13
        P = ' '
        print()
        print(
            'STATUS CODE'.ljust(N, P),
            'COUNT'.rjust(N, P),
            'MEDIAN'.rjust(N, P),
            '(INTERNAL)'.rjust(N, P),
            'AVERAGE'.rjust(N, P),
            '(INTERNAL)'.rjust(N, P),
            '% RIGHT'.rjust(N, P),
        )
        for key in by_got_times:
            request_times = [x[0] for x in by_got_times[key]]
            if len(request_times) <= 2:
                print('Too few datapoints for {!r}'.format(key))
                continue
            median, average, std = _stats(request_times)
            internal_times = [x[1] for x in by_got_times[key] if x[1]]
            imedian, iaverage, istd = _stats(internal_times)
            # print((imedian, iaverage, istd))
            total = len(by_got_matched[key])
            right = 100 * sum([x for x in by_got_matched[key] if x]) / total
            print(
                str(key).ljust(N),
                str(len(by_got_times[key])).rjust(N, P),
                time_fmt(median).rjust(N, P),
                time_fmt(imedian).rjust(N, P),
                time_fmt(average).rjust(N, P),
                time_fmt(iaverage).rjust(N, P),
                number_fmt(right).rjust(N, P),
            )

        print('Ignore hits', ignore_hits)
        print('Not ignore hits', len(cache_hits))

    times = []

    def total_duration():
        if not times:
            return 'na'
        seconds = time.time() - times[0]
        if seconds < 100:
            return '{:.1f} seconds'.format(seconds)
        else:
            return '{:.1f} minutes'.format(seconds / 60)

    def speed_per_second(last=10):
        if not times:
            return 'na'
        if len(times) > last:
            t = time.time() - times[-last]
            L = last
        else:
            t = time.time() - times[0]
            L = len(times)
        return '{:.1f}'.format(L / t)

    def speed_per_minute(last=10):
        if not times:
            return 'na'
        if len(times) > last:
            t = time.time() - times[-last]
            L = last
        else:
            t = time.time() - times[0]
            L = len(times)
        return '{:.1f}'.format(L * 60 / t)

    def get_patiently(*args, **kwargs):
        attempts = kwargs.pop('attempts', 0)
        try:
            t0 = time.time()
            req = requests.get(url, **kwargs, allow_redirects=False)
            t1 = time.time()
            return (t1, t0), req
        except ConnectionError:
            if attempts > 3:
                raise
            time.sleep(1)
            return get_patiently(*args, attempts=attempts + 1, **kwargs)

    with open(csv_file) as f:
        reader = csv.reader(f)
        next(reader)  # header
        jobs = list(reader)

    # jobs=[x for x in jobs if x[1]=='200']

    flattened_jobs = []
    for uri, status, private, count in jobs:
        if only_microsoft_like_symbols:
            if not uri.endswith('.sym'):
                continue
            try:
                if not uri.split('/')[-3].endswith('.pdb'):
                    continue
            except IndexError:
                continue

        for i in range(int(count)):
            flattened_jobs.append((
                uri, status, private, 1
            ))

    random.shuffle(flattened_jobs)

    print(
        'TIME'.ljust(10),
        'INTERNAL'.ljust(10),
        'URL',
    )

    try:
        for i, job in enumerate(flattened_jobs):
            s3_uri = job[0]
            status_code = job[1]

            uri = '/'.join(s3_uri.split('/')[-3:])
            if uri.count('/') != 2:
                # Some junk that got in
                continue
            if ' ' in uri:
                # bad CSV parsing apparently
                continue
            url = urljoin(base_url, uri)

            params = {}
            try:
                symbol, debugid, filename = uri.split('/')
            except ValueError:
                print('BAD uri: {!r}'.format(uri))
                continue

            key = (symbol, debugid)
            if key in code_files_and_ids:
                code_file, code_id = code_files_and_ids[key]
                params['code_file'] = code_file
                params['code_id'] = code_id

            (t1, t0), resp = get_patiently(
                url,
                params=params,
                headers={
                    'debug': 'true',
                }
            )
            try:
                internal_time = float(resp.headers['debug-time'])
                if resp.headers['debug-time'] == '0':
                    ignore_hits += 1
                elif internal_time < 0.01:
                    cache_hits.append(True)
                else:
                    cache_hits.append(False)
                cache_hits = cache_hits[:500]
            except KeyError:
                internal_time = None

            print(
                time_fmt(t1 - t0).ljust(10),
                (
                    internal_time is not None and
                    time_fmt(internal_time) or
                    'n/a'
                ).ljust(10),
                url,
            )

            if cache_hits:
                _cache_hits = len([x for x in cache_hits if x])
                _cache_misses = len([x for x in cache_hits if not x])
                fastcache = 100 * _cache_hits / (
                    _cache_misses + _cache_hits
                )
            else:
                fastcache = 0.0
            out = (
                ' {} of {} -- {} requests/s -- {} requests/min ({}) -- '
                '{:.1f}% fastcache (last {})'.format(
                    format(i + 1, ','),
                    format(uris_count, ','),
                    speed_per_second(),
                    speed_per_minute(),
                    total_duration(),
                    fastcache,
                    len(cache_hits),
                ).center(80, '=')
            )
            print(out, end='')
            print('\r' * len(out), end='')

            times.append(t0)
            jobs_done.append({
                'expect': int(status_code),
                'got': resp.status_code,
                'time': t1 - t0,
                'internal_time': internal_time
            })
    except KeyboardInterrupt:
        print_total_jobs_done(False)
        return 1

    print_total_jobs_done(True)
    return 0


if __name__ == '__main__':
    import sys
    args = sys.argv[1:]
    kwargs = {}
    if '--microsoft-like-only' in args:
        kwargs['only_microsoft_like_symbols'] = True
        args.remove('--microsoft-like-only')
    sys.exit(run(*args, **kwargs))
