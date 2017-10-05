"""The purpose of this file is to generate large symbol.zip files
based on looking at logs in
https://crash-stats.mozilla.com/api/UploadedSymbols/
However, since all files in there are public, a bunch of these queries
have already been made and saved into ./symbols-uploaded/.
"""

import tempfile
import os
import random
import time
import zipfile
import glob
import gzip
import json
import re
import multiprocessing
from urllib.parse import urlparse

import click
import requests
import deco


compression = zipfile.ZIP_DEFLATED


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return '%3.1f%s%s' % (num, unit, suffix)
        num /= 1024.0
    return '%.1f%s%s' % (num, 'Yi', suffix)


def parse_file_size(s):
    parsed = re.findall('(\d+)([gmbk]+)', s)
    if not parsed:
        number = s
        unit = 'b'
    else:
        number, unit = parsed[0]
    number = int(number)
    unit = unit.lower()

    if unit == 'b':
        pass
    elif unit in ('k', 'kb'):
        number *= 1024
    elif unit in ('m', 'mb'):
        number *= 1024 * 1024
    elif unit in ('g', 'gb'):
        number *= 1024 * 1024 * 1024
    else:
        raise NotImplementedError(unit)
    return number


def time_fmt(secs):
    return '{:.2f}s'.format(secs)


@deco.concurrent
def download(uri, save_dir, store):
    url = (
        'https://s3-us-west-2.amazonaws.com/'
        'org.mozilla.crash-stats.symbols-public/'
    ) + uri.split(',', 1)[1]
    t0 = time.time()
    response = requests.get(url)
    path = uri.split(',', 1)[1].replace('v1/', '')
    dirname = os.path.join(save_dir, os.path.dirname(path))
    os.makedirs(dirname, exist_ok=True)
    basename = os.path.basename(path)
    fullpath = os.path.join(dirname, basename)
    print(
        response.status_code,
        sizeof_fmt(int(response.headers['Content-Length'])).ljust(10),
        urlparse(url).path.split('/v1')[1],
    )
    with open(fullpath, 'wb') as f:
        f.write(response.content)
    t1 = time.time()
    store[uri] = (fullpath, t1 - t0, int(response.headers['Content-Length']))


def _get_index(save_dir, days=0, max_size=None, silent=False):
    # Pick a random file from the ./symbols-uploaded/ directory
    symbols_uploaded_dir = os.path.join(
        os.path.dirname(__file__),
        'symbols-uploaded'
    )
    symbols_uploaded_file = random.choice(
        glob.glob(os.path.join(symbols_uploaded_dir, '*.json.gz'))
    )
    print("SYMBOLS_UPLOADED_FILE:", symbols_uploaded_file)
    with gzip.open(symbols_uploaded_file, 'rb') as f:
        uploaded = json.loads(f.read().decode('utf-8'))
    all_uploads = uploaded['hits']
    possible = {}
    for i, bundle in enumerate(all_uploads):
        if max_size is not None and bundle['size'] > max_size:
            continue
        wouldbe_name = _make_filepath(save_dir, bundle)
        saved_already = os.path.isfile(wouldbe_name)
        if not silent:
            print(
                str(i + 1).ljust(4),
                bundle['date'].ljust(37),
                sizeof_fmt(bundle['size']).ljust(10),
                'saved already' if saved_already else ''
            )
        if not saved_already:
            possible[i] = (bundle['date'], bundle['size'])

    if not possible:
        raise Exception('No possible zip files')
    if silent:
        preferred = None
    else:
        preferred = input('Which one? [blank for random]: ')
    if not preferred:
        preferred = random.choice(list(possible.keys()))
    else:
        preferred = int(preferred) - 1
    print(
        'Picking {} ({})'.format(
            possible[preferred][0],
            sizeof_fmt(possible[preferred][1])
        )
    )
    print()
    return all_uploads[preferred]


@deco.synchronized
def download_all(urls, save_dir):
    print('Downloading into', save_dir)
    downloaded = {x: False for x in urls}
    for url in urls:
        if url.endswith('/'):
            print('Bad URL (ignoring) {}'.format(url))
        else:
            download(url, save_dir, downloaded)
    return downloaded


def _make_filepath(save_dir, bundle):
    date = bundle['date'].split('.')[0].replace(':', '_')
    return os.path.join(
        save_dir,
        'symbols-{date}.zip'.format(date=date)
    )


_default_save_dir = os.path.join(tempfile.gettempdir(), 'massive-symbol-zips')


@click.command()
@click.option(
    '--save-dir',
    help='Where all .zip files get saved (default {})'.format(
        _default_save_dir,
    )
)
@click.option(
    '--max-size',
    help='Max size of files to upload (default is no limit)',
)
@click.option(
    '--silent',
    help='Will not prompt for an input and use random choice if need be',
    is_flag=True,
)
def run(save_dir=None, max_size=None, silent=False):
    if max_size:
        max_size = parse_file_size(max_size)
        print(
            'Max. size filter:',
            sizeof_fmt(max_size),
        )
    save_dir = save_dir or _default_save_dir
    if not os.path.isdir(save_dir):
        os.makedirs(save_dir, exist_ok=True)
    bundle = _get_index(save_dir, max_size=max_size, silent=silent)
    all_symbol_urls = []
    all_symbol_urls.extend(bundle['content'].get('added', []))
    all_symbol_urls.extend(bundle['content'].get('existed', []))
    print(len(all_symbol_urls), 'URLs to download')
    with tempfile.TemporaryDirectory(prefix='symbols') as tmpdirname:
        t0 = time.time()
        downloaded = download_all(all_symbol_urls, tmpdirname)
        t1 = time.time()
        save_filepath = _make_filepath(save_dir, bundle)
        total_time_took = 0.0
        total_size = 0
        sizes = []
        times = []
        with zipfile.ZipFile(save_filepath, mode='w') as zf:
            for uri, (fullpath, time_took, size) in downloaded.items():
                total_time_took += time_took
                times.append(time_took)
                total_size += size
                sizes.append(size)
                if fullpath:
                    path = uri.split(',')[1].replace('v1/', '')
                    assert os.path.isfile(fullpath)
                    zf.write(
                        fullpath,
                        arcname=path,
                        compress_type=zipfile.ZIP_DEFLATED,
                    )

        print()
        P = 30
        print(
            'TO'.ljust(P),
            save_filepath
        )
        print(
            '# CPUS:'.ljust(P),
            multiprocessing.cpu_count(),
        )
        print(
            'Sum time took:'.ljust(P),
            time_fmt(total_time_took).ljust(P),
            'Download speed:'.ljust(P),
            sizeof_fmt(sum(sizes) / sum(times)) + '/s'
        )
        print(
            'Total time took:'.ljust(P),
            time_fmt(t1 - t0).ljust(P),
            'Download speed:'.ljust(P),
            sizeof_fmt(sum(sizes) / (t1 - t0)) + '/s',
        )
        print(
            'Total size (files):'.ljust(P),
            total_size,
            '({})'.format(sizeof_fmt(total_size)),
        )
        print(
            'Total size:'.ljust(P),
            os.stat(save_filepath).st_size,
            '({})'.format(sizeof_fmt(os.stat(save_filepath).st_size)),
        )
        print(
            'Bundle size:'.ljust(P),
            bundle['size'],
            '({})'.format(sizeof_fmt(bundle['size'])),
        )

    return 0


if __name__ == '__main__':
    run()
