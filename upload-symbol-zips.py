"""The purpose of this script is to upload random .zip files.
By default you send them to http://localhost:8000/upload
By default it only uploads 1.
"""

import re
import os
import random
import tempfile
import time
import glob
from urllib.parse import urlparse

import click
import requests


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return '%3.1f%s%s' % (num, unit, suffix)
        num /= 1024.0
    return '%.1f%s%s' % (num, 'Yi', suffix)


_default_zips_dir = os.path.join(tempfile.gettempdir(), 'massive-symbol-zips')


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


def upload(filepath, url, auth_token):
    basename = os.path.basename(filepath)
    click.echo(click.style(
        'About to upload {} ({}) to {}'.format(
            basename,
            sizeof_fmt(os.stat(filepath).st_size),
            url,
        ),
        fg='green'
    ))
    t0 = time.time()
    response = requests.post(
        url,
        files={basename: open(filepath, 'rb')},
        headers={
            'auth-token': auth_token,
        },
        timeout=30,
    )
    t1 = time.time()
    if response.status_code == 201:
        click.echo(click.style(
            'Took {} seconds to upload {} ({} - {}/s)'.format(
                round(t1 - t0, 1),
                basename,
                sizeof_fmt(os.stat(filepath).st_size),
                sizeof_fmt(os.stat(filepath).st_size / (t1 - t0))
            ),
            fg='green'
        ))
        # upload_id = response.json()['upload']['id']
        # time.sleep(1)
        # query_url = url + '{}/'.format(upload_id)
        # response = requests.get(
        #     query_url,
        #     headers={'auth-token': auth_token},
        # )
        # print('Result of querying '.ljust(80, '-'))
        # pprint(response.json())
        # print('-' * 80)
    else:
        click.echo(response.json())
        click.echo(
            click.style(
                'Failed to upload! Status: {}'.format(response.status_code),
                fg='red'
            )
        )


@click.command()
@click.option(
    '--zips-dir',
    help='Where all .zip files were saved (default {})'.format(
        _default_zips_dir,
    )
)
@click.option('--max-size')
@click.option('-n', '--number', default=1, type=int)
@click.argument('url', nargs=1, required=False)
def run(
    url=None,
    number=1,
    zips_dir=None,
    max_size=None
):
    url = url or 'http://localhost:8000/upload/'
    if not urlparse(url).path:
        url += '/upload/'
    elif urlparse(url).path == '/':
        url += 'upload/'
    assert url.endswith('/upload/'), url
    zips_dir = zips_dir or _default_zips_dir
    max_size = max_size or '250m'
    max_size_bytes = parse_file_size(max_size)
    try:
        auth_token = os.environ['AUTH_TOKEN']
    except KeyError:
        click.echo(
            click.style(
                'You have to set environment variable AUTH_TOKEN first.',
                fg='red'
            )
        )
        return 1
    if not os.path.isdir(zips_dir):
        click.echo(
            click.style(
                'Directory {} does not exist'.format(zips_dir),
                fg='red'
            )
        )
        return 2
    zips = glob.glob(os.path.join(zips_dir, '*.zip'))
    if not zips:
        click.echo(
            click.style(
                'Directory {} contains no .zip files'.format(zips_dir),
                fg='red'
            )
        )
        return 3

    zips = [x for x in zips if os.stat(x).st_size < max_size_bytes]
    if not zips:
        click.echo(
            click.style(
                'There fewer than {} files less than {}'.format(
                    number,
                    max_size,
                ),
                fg='red'
            )
        )
        return 4

    random.shuffle(zips)
    for zip_ in zips[:number]:
        upload(zip_, url, auth_token)

    return 0


if __name__ == '__main__':
    run()
