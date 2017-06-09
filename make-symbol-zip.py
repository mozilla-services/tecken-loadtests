"""The purpose of this file is to generate large symbol.zip files
based on looking at logs in
https://crash-stats.mozilla.com/api/UploadedSymbols/
which requires an API token.
"""

import datetime
import tempfile
import os
import time
import zipfile
from urllib.parse import urlencode

import requests
import deco

import zlib  # just check that it worked!


compression = zipfile.ZIP_DEFLATED


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
    print(url, response.status_code)
    with open(fullpath, 'wb') as f:
        f.write(response.content)
    t1 = time.time()
    store[uri] = (fullpath, t1 - t0, int(response.headers['Content-Length']))


def _get_index(auth_token):
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
    return all_uploads[-1]


@deco.synchronized
def download_all(urls, save_dir):
    print('Downloading into', save_dir)
    # urls=urls[:16]
    downloaded = {x: False for x in urls}
    for url in urls:
        download(url, save_dir, downloaded)
    # print('FINISHED LOOPING')
    # print(downloaded)
    return downloaded


def run(*args):
    auth_token = os.environ['AUTH_TOKEN']
    bundle = _get_index(auth_token)
    all_symbol_urls = []
    all_symbol_urls.extend(bundle['content'].get('added', []))
    all_symbol_urls.extend(bundle['content'].get('existed', []))
    print(len(all_symbol_urls), 'URLs to download')
    with tempfile.TemporaryDirectory(prefix='symbols') as tmpdirname:
        downloaded = download_all(all_symbol_urls, tmpdirname)
        date = bundle['date'].split('.')[0].replace(':', '_')
        save_dir = os.path.join(tempfile.gettempdir(), 'massive-symbol-zips')
        if not os.path.isdir(save_dir):
            os.mkdir(save_dir)
        save_filepath = os.path.join(
            save_dir,
            'symbols-{date}.zip'.format(date=date)
        )
        total_time_took = 0.0
        total_size = 0
        with zipfile.ZipFile(save_filepath, mode='w') as zf:
            t0 = time.time()
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
            t1 = time.time()

        print()
        P = 25
        print('TO'.ljust(P), save_filepath)
        print('Sum time took (seconds):'.ljust(P), round(total_time_took, 1))
        print('Total time took (seconds):'.ljust(P), round(t1 - t0, 1))
        print('Total size (files):'.ljust(P), total_size)
        print('DONE! Total size:'.ljust(P), os.stat(save_filepath).st_size)
        print('Bundle size:'.ljust(P), bundle['size'])


    return 0


if __name__ == '__main__':
    import sys
    sys.exit(run(*sys.argv[1:]))
