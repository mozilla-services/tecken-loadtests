from __future__ import print_function  # in case you use py2

import datetime
import os
import time
import json
import copy
import random
import tempfile
from urllib.parse import urlparse
from pprint import pprint

import click
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


def post_patiently(url, **kwargs):
    attempts = kwargs.pop('attempts', 0)
    payload = kwargs['json']
    try:
        t0 = time.time()
        options = {
            'headers': {
                'Debug': 'true',
            },
        }
        parsed = urlparse(url)
        if parsed.scheme == 'https' and parsed.netloc == 'prod.tecken.dev':
            options['verify'] = False
        req = requests.post(url, json=payload, **options)
        if req.status_code == 502 and 'localhost:8000' in url:
            # When running against, http://localhost:8000 and the Django
            # server restarts, you get a 502 error. Just try again
            # a little later.
            print("OH NO!! 502 Error")
            raise ConnectionError('a hack')
        if req.status_code != 200:
            print('URL:', url)
            print('PAYLOAD:', json.dumps(payload))
        assert req.status_code == 200, req.status_code
        r = req.json()
        t1 = time.time()
        return (t1, t0), r
    except ConnectionError:
        if attempts > 3:
            raise
        time.sleep(2)
        return post_patiently(url, attempts=attempts + 1, **kwargs)


@click.command()
@click.option('--debug-only', '-d', default=False, is_flag=True, help="Only output the 'debug' data")
@click.argument('url')
@click.argument('file', nargs=-1)
def run(url, file, debug_only=False):


    # print(repr(url))
    # print(file)
    # raise Exception
    # files_count = wc_dir(input_dir)
    # print(format(files_count, ','), 'FILES')
    # print()
    # all_debugs = []
    #
    # def print_total_debugs(finished):
    #     print('\n')
    #     if finished:
    #         print('TOTAL', len(all_debugs), 'JOBS DONE')
    #     else:
    #         print('TOTAL SO FAR', len(all_debugs), 'JOBS DONE')
    #     one = copy.deepcopy(all_debugs[0])
    #     listify(one)
    #     for debug in all_debugs:
    #         appendify(debug, one)
    #
    #     P = 23
    #     N = 15
    #     print(
    #         'KEY'.ljust(P),
    #         'SUM'.rjust(N),
    #         'AVG'.rjust(N),
    #         'MEDIAN'.rjust(N),
    #         'STD-DEV'.rjust(N),
    #     )
    #     printify(one, P, N)
    #
    #     print('\n')
    #     print('IN CONCLUSION...')
    #     if one['downloads']['count'] and sum(one['downloads']['time']):
    #         print(
    #             'Final Average Download Speed'.ljust(P),
    #             '{}/s'.format(
    #                 sizeof_fmt(
    #                     sum(one['downloads']['size']) /
    #                     sum(one['downloads']['time'])
    #                 )
    #             ),
    #         )
    #     total_time_everything_else = (
    #         sum(one['time']) -
    #         sum(one['downloads']['time']) -
    #         sum(one['cache_lookups']['time'])
    #     )
    #     print(
    #         'Total time NOT downloading or querying cache  ',
    #         time_fmt(total_time_everything_else)
    #     )
    #     print(
    #         'Average time NOT downloading or querying cache',
    #         time_fmt(total_time_everything_else / len(one['time']))
    #     )
    #
    # times = []
    #
    # def total_duration():
    #     if not times:
    #         return 'na'
    #     seconds = time.time() - times[0]
    #     if seconds < 100:
    #         return '{:.1f} seconds'.format(seconds)
    #     else:
    #         return '{:.1f} minutes'.format(seconds / 60)
    #
    # def speed_per_second(last=10):
    #     if not times:
    #         return 'na'
    #     if len(times) > last:
    #         t = time.time() - times[-last]
    #         L = last
    #     else:
    #         t = time.time() - times[0]
    #         L = len(times)
    #     return '{:.1f}'.format(L / t)
    #
    # def speed_per_minute(last=10):
    #     if not times:
    #         return 'na'
    #     if len(times) > last:
    #         t = time.time() - times[-last]
    #         L = last
    #     else:
    #         t = time.time() - times[0]
    #         L = len(times)
    #     return '{:.1f}'.format(L * 60 / t)
    #
    # files = [os.path.join(input_dir, x) for x in os.listdir(input_dir)]
    # random.shuffle(files)
    #
    # now = datetime.datetime.now().strftime('%Y%m%d')
    # logfile_path = os.path.join(
    #     tempfile.gettempdir(),
    #     'symbolication-' + now + '.log'
    # )
    # print('All verbose logging goes into:', logfile_path)
    # print()
    for i, fp in enumerate(file):
        with open(fp) as f:
            payload = json.loads(f.read())

            # print("PAYLOAD (as JSON)", file=logfile)
            # print('-' * 79, file=logfile)
            # print(json.dumps(payload), file=logfile)

            (t1, t0), r = post_patiently(url, json=payload)
            # print(r['knownModules'])
            # t0 = time.time()
            # req = requests.post(url, json=payload)
            # r = req.json()
            # t1 = time.time()
            # print(r)
            # print(file=logfile)
            # print("RESPONSE (as JSON)", file=logfile)
            # print('-' * 79, file=logfile)
            # print(json.dumps(r), file=logfile)
            # print('-' * 79, file=logfile)
            # for j, combo in enumerate(payload['memoryMap']):
            #     print(combo, '-->', r['knownModules'][j], file=logfile)
            # print('=' * 79, file=logfile)
            # print(file=logfile)

            if debug_only:
                print(json.dumps(r['debug'], indent=3, sort_keys=True))
            else:
                print(json.dumps(r, indent=3, sort_keys=True))
                # pprint(r)
            # print(r)

            # debug = r['debug']
            # debug['modules'].pop('stacks_per_module')
            # times.append(t0)
            # debug['loader_time'] = t1 - t0
            # all_debugs.append(debug)
        #     _downloads = (
        #         '{} downloads ({}, {})'.format(
        #             debug['downloads']['count'],
        #             time_fmt(debug['downloads']['time']),
        #             sizeof_fmt(debug['downloads']['size']),
        #         )
        #     )
        #     _cache_lookups = (
        #         '{} ({}) cache lookup{} ({} -- {}/lookup)'.format(
        #             debug['cache_lookups']['count'],
        #             (
        #                 debug['modules']['count'] -
        #                 debug['downloads']['count']
        #             ),
        #             debug['cache_lookups']['count'] > 1 and 's' or '',
        #             time_fmt(debug['cache_lookups']['time']),
        #             time_fmt(
        #                 debug['cache_lookups']['time'] /
        #                 debug['cache_lookups']['count']
        #             ),
        #         )
        #     )
        #     print(_downloads.ljust(35), _cache_lookups)
        #     out = (
        #         ' {} of {} -- {} requests/minute ({} req/s) ({}) '.format(
        #             format(i + 1, ','),
        #             format(files_count, ','),
        #             speed_per_minute(),
        #             speed_per_second(),
        #             total_duration(),
        #         ).center(80, '=')
        #     )
        #     print(out, end='')
        #     print('\r' * len(out), end='')
        #     time.sleep(0.05)
        # if limit is not None and i == limit - 1:
        #     break

    return 0


if __name__ == '__main__':
    run()
