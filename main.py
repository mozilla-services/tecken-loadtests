from __future__ import print_function  # in case you use py2

import os
import time
import json
import copy
import random

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
    return '{:.3f}s'.format(x)


def wc_dir(fd):
    return len(os.listdir(fd))
    # with open(fd) as f:
    #     return f.read().count('\n')


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


def printify(objects, p=30, n=10, prefix=''):
    for key in sorted(objects):
        value = objects[key]
        if isinstance(value, dict):
            printify(value, p=p, n=n, prefix=prefix + key + '.')
        else:
            formatter = number_fmt
            if key == 'size':
                formatter = sizeof_fmt
            elif key.endswith('time'):
                formatter = time_fmt
            median, average, stddev = _stats(value)
            print(
                (prefix + key).ljust(p),
                formatter(sum(value)).rjust(n),
                formatter(average).rjust(n),
                formatter(median).rjust(n),
                formatter(stddev).rjust(n),
            )


def _stats(r):
    # returns the median, average and standard deviation of a sequence
    tot = sum(r)
    avg = tot/len(r)
    sdsq = sum([(i-avg)**2 for i in r])
    s = list(r)
    s.sort()
    return s[len(s)//2], avg, (sdsq/(len(r)-1 or 1))**.5


def run(input_dir, url):
    files_count = wc_dir(input_dir)
    print(format(files_count, ','), 'FILES')
    print('\n')
    all_debugs = []

    def print_total_debugs(finished):
        print('\n')
        if finished:
            print('TOTAL', len(all_debugs), 'JOBS DONE')
        else:
            print('TOTAL SO FAR', len(all_debugs), 'JOBS DONE')
        one = copy.deepcopy(all_debugs[0])
        listify(one)
        for debug in all_debugs:
            appendify(debug, one)

        P = 23
        N = 15
        print(
            'KEY'.ljust(P),
            'SUM'.rjust(N),
            'AVG'.rjust(N),
            'MEDIAN'.rjust(N),
            'STD-DEV'.rjust(N),
        )
        printify(one, P, N)

        print('\n')
        print('IN CONCLUSION...')
        if one['downloads']['count']:
            print(
                'Final Download Speed'.ljust(P),
                '{}/s'.format(
                    sizeof_fmt(
                        sum(one['downloads']['size']) /
                        sum(one['downloads']['time'])
                    )
                ),
            )
        print(
            'Final Cache Speed'.ljust(P),
            '{}/s'.format(
                sizeof_fmt(
                    sum(one['cache_lookups']['size']) /
                    sum(one['cache_lookups']['time'])
                )
            ),
        )
        total_time_everything_else = (
            sum(one['time']) -
            sum(one['downloads']['time']) -
            sum(one['cache_lookups']['time'])
        )
        print(
            'Total time NOT downloading or querying cache  ',
            time_fmt(total_time_everything_else)
        )
        print(
            'Average time NOT downloading or querying cache',
            time_fmt(total_time_everything_else / len(one['time']))
        )

    times = []

    def total_duration():
        if not times:
            return 'na'
        seconds = time.time() - times[0]
        if seconds < 100:
            return '{:.1f} seconds'.format(seconds)
        else:
            return '{:.1f} minutes'.format(seconds / 60)

    def speed_per_minute():
        if not times:
            return 'na'
        # XXX the speed should be based on the last 10, not all
        t = time.time() - times[0]
        return '{:.1f}'.format(len(times) * 60 / t)

    def post_patiently(*args, **kwargs):
        attempts = kwargs.pop('attempts', 0)
        try:
            t0 = time.time()
            req = requests.post(url, json=payload)
            r = req.json()
            t1 = time.time()
            return (t1, t0), r
        except ConnectionError:
            if attempts > 3:
                raise
            time.sleep(1)
            return post_patiently(*args, attempts=attempts + 1, **kwargs)

    files = [os.path.join(input_dir, x) for x in os.listdir(input_dir)]
    random.shuffle(files)
    try:
        for i, fp in enumerate(files):
            with open(fp) as f:
                payload = json.loads(f.read())
                payload['debug'] = True
                print(
                    ' {} of {} -- {} requests/minute ({}) '.format(
                        format(i + 1, ','),
                        format(files_count, ','),
                        speed_per_minute(),
                        total_duration(),
                    ).center(80, '=')
                )
                print(payload)

                (t1, t0), r = post_patiently(url, json=payload)
                # t0 = time.time()
                # req = requests.post(url, json=payload)
                # r = req.json()
                # t1 = time.time()
                # print(r)
                debug = r['debug']
                debug['modules'].pop('stacks_per_module')
                times.append(t0)
                debug['loader_time'] = t1 - t0
                all_debugs.append(debug)
                print()
                # if i>1:
                #     break
                time.sleep(0.1)
    except KeyboardInterrupt:
        print_total_debugs(False)
        return 1

    print_total_debugs(True)
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(run(*sys.argv[1:]))
