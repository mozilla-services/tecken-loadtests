#!/usr/bin/env python

"""
Loop over a bunch of .zip files in a directory, for each, read into
memory and then measure how long it takes to unzip and extract it to disk.
"""

import random
import os
import zipfile
import glob
import tempfile
import time
import statistics
from io import BytesIO

import click


def dump_and_extract(root_dir, file_buffer, name):
    if name.lower().endswith('.zip'):
        zf = zipfile.ZipFile(file_buffer)
        zf.extractall(root_dir)
    else:
        raise ValueError(os.path.splitext(name)[1])
    return root_dir


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return '%3.1f%s%s' % (num, unit, suffix)
        num /= 1024.0
    return '%.1f%s%s' % (num, 'Yi', suffix)


def time_fmt(t):
    return '%.3fs' % t


@click.command()
@click.argument('directory', nargs=1)
def run(directory):
    files = glob.glob(os.path.join(directory, '*.zip'))
    random.shuffle(files)
    # print(files)
    times = []
    for fn in files:
        name = os.path.basename(fn)
        with open(fn, 'rb') as f:
            in_memory = f.read()
        size = len(in_memory)
        with tempfile.TemporaryDirectory() as tmpdir:
            t0 = time.time()
            dump_and_extract(tmpdir, BytesIO(in_memory), name)
            t1 = time.time()
        times.append((size / (t1 - t0), size, t1 - t0))
    times.sort()
    speeds = []
    for speed, size, time_ in times:
        print(
            (sizeof_fmt(speed) + '/s').ljust(20),
            sizeof_fmt(size).ljust(20),
            time_fmt(time_),
        )
        speeds.append(speed)

    print('\n')
    avg_speed = statistics.mean(speeds)
    print(
        "Average speed:",
        sizeof_fmt(avg_speed) + '/s',
    )
    med_speed = statistics.median(speeds)
    print(
        "Median speed: ",
        sizeof_fmt(med_speed) + '/s',
    )


if __name__ == '__main__':
    run()
