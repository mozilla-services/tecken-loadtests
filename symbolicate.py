from __future__ import print_function  # in case you use py2

import os
import time
import json
from urllib.parse import urlparse

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
@click.option(
    '--debug-only', '-d',
    default=False,
    is_flag=True,
    help="Only output the 'debug' data"
)
@click.argument('url')
@click.argument('file', nargs=-1)
def run(url, file, debug_only=False):

    for i, fp in enumerate(file):
        print(
            'Posting {} ({} of {})...'.format(
                fp,
                i + 1,
                len(file)
            )
        )
        with open(fp) as f:
            payload = json.loads(f.read())

            (t1, t0), r = post_patiently(url, json=payload)

            if debug_only:
                print(json.dumps(r['debug'], indent=3, sort_keys=True))
            else:
                print(json.dumps(r, indent=3, sort_keys=True))

    return 0


if __name__ == '__main__':
    run()
