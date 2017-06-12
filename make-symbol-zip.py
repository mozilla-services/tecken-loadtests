"""The purpose of this file is to generate large symbol.zip files
based on looking at logs in
https://crash-stats.mozilla.com/api/UploadedSymbols/
which requires an API token.
"""

import datetime
import tempfile
import os
import random
import time
import zipfile
from urllib.parse import urlencode

import requests
import deco


compression = zipfile.ZIP_DEFLATED


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return '%3.1f%s%s' % (num, unit, suffix)
        num /= 1024.0
    return '%.1f%s%s' % (num, 'Yi', suffix)


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
        url,
    )
    with open(fullpath, 'wb') as f:
        f.write(response.content)
    t1 = time.time()
    store[uri] = (fullpath, t1 - t0, int(response.headers['Content-Length']))


def _get_index(auth_token, save_dir):
    url = 'https://crash-stats.mozilla.com/api/UploadedSymbols/'
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    url += '?' + urlencode({
        'start_date': today,
        'end_date': today,
        'user_search': 'coop',  # RelEng
    })
    response = requests.get(url, headers={'Auth-Token': auth_token})
    assert response.status_code == 200, response.status_code
    all_uploads = response.json()['hits']
    # index = random.randint(0, len(all_uploads))
    possible = {}
    for i, bundle in enumerate(all_uploads):
        wouldbe_name = _make_filepath(save_dir, bundle)
        saved_already = os.path.isfile(wouldbe_name)
        print(
            str(i + 1).ljust(4),
            bundle['date'].ljust(37),
            sizeof_fmt(bundle['size']).ljust(10),
            'saved already' if saved_already else ''
        )
        if not saved_already:
            possible[i] = (bundle['date'], bundle['size'])

    preferred = input('Which one? [blank for random]: ')
    if not preferred:
        preferred = random.choice(list(possible.keys()))
    else:
        preferred = int(preferred)
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
    # urls=urls[:16]
    downloaded = {x: False for x in urls}
    for url in urls:
        download(url, save_dir, downloaded)
    return downloaded


def _make_filepath(save_dir, bundle):
    date = bundle['date'].split('.')[0].replace(':', '_')
    return os.path.join(
        save_dir,
        'symbols-{date}.zip'.format(date=date)
    )


def run(*args):
    auth_token = os.environ['AUTH_TOKEN']
    save_dir = os.path.join(tempfile.gettempdir(), 'massive-symbol-zips')
    if not os.path.isdir(save_dir):
        os.mkdir(save_dir)
    bundle = _get_index(auth_token, save_dir)
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
        with zipfile.ZipFile(save_filepath, mode='w') as zf:
            for uri, (fullpath, time_took, size) in downloaded.items():
                total_time_took += time_took
                total_size += size
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
            'Sum time took (seconds):'.ljust(P),
            round(total_time_took, 1)
        )
        print(
            'Total time took (seconds):'.ljust(P),
            round(t1 - t0, 1)
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
    import sys
    sys.exit(run(*sys.argv[1:]))
