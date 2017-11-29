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
import shutil
from io import BytesIO
from contextlib import contextmanager

import click


def dump_and_extract(root_dir, file_buffer):
    zf = zipfile.ZipFile(file_buffer)
    zf.extractall(root_dir)
    print(root_dir)
    total_files = 0
    total_dirs = 0
    for root, dirs, files in os.walk(root_dir):
        total_files += len(files)
        total_dirs += len(dirs)

    return total_dirs, total_files


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return '%3.1f%s%s' % (num, unit, suffix)
        num /= 1024.0
    return '%.1f%s%s' % (num, 'Yi', suffix)


def time_fmt(t):
    return '%.3fs' % t


@contextmanager
def maketempdir(root, prefix='prefix'):
    def randstr():
        return prefix + str(int(random.random() * 100000))
    fn = os.path.join(root, randstr())
    os.mkdir(fn)
    yield fn
    shutil.rmtree(fn)


@click.command()
@click.option(
    '-t', '--tmp-dir-root',
    default=None,
    help='Root for the temporary directories'
)
@click.argument('directory', nargs=1)
def run(directory, tmp_dir_root=None):
    if tmp_dir_root is None:
        tmp_dir_root = tempfile.gettempdir()
    files = glob.glob(os.path.join(directory, '*.zip'))
    random.shuffle(files)
    times = []
    speeds = []
    files_created = []
    dirs_created = []
    for fn in files:
        with open(fn, 'rb') as f:
            in_memory = f.read()
        size = len(in_memory)
        with maketempdir(tmp_dir_root) as tmpdir:
            t0 = time.time()
            tf, td = dump_and_extract(tmpdir, BytesIO(in_memory))
            t1 = time.time()
            files_created.append(tf)
            dirs_created.append(td)
        time_ = t1 - t0
        speed = size / time_
        print(
            (sizeof_fmt(speed) + '/s').ljust(20),
            sizeof_fmt(size).ljust(20),
            time_fmt(time_),
        )
        times.append((speed, size, time_))
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
    print()
    print(
        "Average files created:      ",
        int(statistics.mean(files_created))
    )
    print(
        "Average directories created:",
        int(statistics.mean(dirs_created))
    )


if __name__ == '__main__':
    run()
