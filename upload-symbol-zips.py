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
from json.decoder import JSONDecodeError

import click
import requests
from requests.exceptions import ReadTimeout


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


def upload(filepath, url, auth_token, max_retries=5):
    basename = os.path.basename(filepath)
    click.echo(click.style(
        'About to upload {} ({}) to {}'.format(
            filepath,
            sizeof_fmt(os.stat(filepath).st_size),
            url,
        ),
        fg='green'
    ))
    retries = 0
    while True:
        try:
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
            break
        except ReadTimeout as exception:
            t1 = time.time()
            retries += 1
            if retries >= max_retries:
                raise
            click.echo(click.style(
                'Retrying (after {:.1f}s) due to {}: {}'.format(
                    t1 - t0,
                    exception.__class__.__name__,
                    exception,
                ),
                fg='yellow'
            ))

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
        return True
    else:
        click.echo(click.style(
            'Failed to upload! Status code: {}'.format(response.status_code)
        ))
        try:
            click.echo(response.json())
        except JSONDecodeError:
            click.echo(response.content)
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
@click.option('--max-size', default='250mb', help=(
    'Max size of files to attempt to upload.'
))
@click.option('-n', '--number', default=1, type=int)
@click.option('--delete-uploaded-file', is_flag=True, help=(
    'Delete the file that was successfully uploaded.'
))
@click.argument('url', nargs=1, required=False)
def run(
    url=None,
    number=1,
    zips_dir=None,
    max_size=None,
    delete_uploaded_file=False,
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
        raise click.ClickException(
            'You have to set environment variable AUTH_TOKEN first.'
        )
    if not os.path.isdir(zips_dir):
        raise click.ClickException(
            'Directory {} does not exist'.format(zips_dir)
        )
    zips = glob.glob(os.path.join(zips_dir, '*.zip'))
    if not zips:
        raise click.ClickException(
            'Directory {} contains no .zip files'.format(zips_dir)
        )

    zips = [x for x in zips if os.stat(x).st_size < max_size_bytes]
    if not zips:
        raise click.ClickException(
            'There fewer than {} files less than {}'.format(
                number,
                max_size,
            )
        )

    random.shuffle(zips)
    upload_failures = 0
    for zip_ in zips[:number]:
        successful = upload(zip_, url, auth_token)
        if not successful:
            upload_failures += 1
        if successful and delete_uploaded_file:
            click.style(
                'Deleting zip file {}'.format(
                    zip_
                )
            )
            os.remove(zip_)

    if upload_failures:
        raise click.ClickException(
            '{} files failed to upload'.format(upload_failures)
        )


if __name__ == '__main__':
    run()
