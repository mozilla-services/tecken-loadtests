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
from requests.exceptions import ReadTimeout, ConnectionError


class BadGatewayError(Exception):
    """happens when you get a 502 error from the server"""


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


def upload(filepath, url, auth_token, max_retries=5, timeout=300):
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
    sleeptime = 5
    while True:
        try:
            t0 = time.time()
            response = requests.post(
                url,
                files={basename: open(filepath, 'rb')},
                headers={
                    'auth-token': auth_token,
                },
                timeout=timeout,
            )
            if response.status_code == 502:
                # force a re-attempt
                raise BadGatewayError(response.content)
            if response.status_code == 408 or response.status_code == 504:
                # Nginx calmly says Gunicorn timed out. Force a re-attempt.
                raise ReadTimeout(response.status_code)
            t1 = time.time()
            break
        except (ReadTimeout, BadGatewayError) as exception:
            t1 = time.time()
            retries += 1
            click.echo(click.style(
                'Deliberately sleeping for {} seconds'.format(sleeptime),
                fg='yellow'
            ))
            time.sleep(sleeptime)
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


def upload_by_download_url(
    url,
    auth_token,
    download_url,
    content_length=None,
    max_retries=5,
    timeout=300
):
    click.echo(click.style(
        'About to upload {} ({}) to {}'.format(
            download_url,
            'n/a' if content_length is None else sizeof_fmt(content_length),
            url,
        ),
        fg='green'
    ))
    retries = 0
    sleeptime = 5
    while True:
        try:
            t0 = time.time()
            response = requests.post(
                url,
                data={'url': download_url},
                headers={
                    'auth-token': auth_token,
                },
                timeout=timeout,
            )
            if response.status_code == 502:
                # force a re-attempt
                raise BadGatewayError(response.content)
            if response.status_code == 408 or response.status_code == 504:
                # Nginx calmly says Gunicorn timed out. Force a re-attempt.
                raise ReadTimeout(response.status_code)
            t1 = time.time()
            break
        except (ReadTimeout, BadGatewayError) as exception:
            t1 = time.time()
            retries += 1
            click.echo(click.style(
                'Deliberately sleeping for {} seconds'.format(sleeptime),
                fg='yellow'
            ))
            time.sleep(sleeptime)
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
        if content_length is None:
            click.echo(click.style(
                'Took {} seconds to upload by download url {}'.format(
                    round(t1 - t0, 1),
                    download_url,
                ),
                fg='green'
            ))
        else:
            click.echo(click.style(
                'Took {} seconds to upload by download url '
                '{} ({} - {}/s)'.format(
                    round(t1 - t0, 1),
                    download_url,
                    sizeof_fmt(content_length),
                    sizeof_fmt(content_length / (t1 - t0))
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
@click.option('--max-size', default='1000mb', help=(
    'Max size of files to attempt to upload.'
))
@click.option('-n', '--number', default=1, type=int)
@click.option('-t', '--timeout', default=300, type=int)
@click.option('--delete-uploaded-file', is_flag=True, help=(
    'Delete the file that was successfully uploaded.'
))
@click.option('-d', '--download-url', help=(
    'Instead of upload a local file, post a URL to download'
))
@click.argument('url', nargs=1, required=False)
def run(
    url=None,
    number=1,
    zips_dir=None,
    max_size=None,
    delete_uploaded_file=False,
    download_url=None,
    timeout=300,
):
    url = url or 'http://localhost:8000/upload/'
    if not urlparse(url).path:
        url += '/upload/'
    elif urlparse(url).path == '/':
        url += 'upload/'
    assert url.endswith('/upload/'), url
    try:
        auth_token = os.environ['AUTH_TOKEN']
    except KeyError:
        raise click.ClickException(
            'You have to set environment variable AUTH_TOKEN first.'
        )

    max_size = max_size or '250m'
    max_size_bytes = parse_file_size(max_size)

    if download_url:
        if download_url.endswith('index.json'):
            get = requests.get(download_url)
            assert get.status_code == 200, get.status_code
            files = get.json()['files']
            files = [x for x in files if x['size'] < max_size_bytes]
            file = random.choice(files)
            download_url = download_url.replace('index.json', file['uri'])
            content_length = file['size']
        else:
            try:
                head = requests.head(download_url)
                if head.status_code >= 300 and head.status_code < 400:
                    head = requests.head(head.headers['location'])
                assert head.status_code == 200, head.status_code
                content_length = int(head.headers['Content-Length'])
            except ConnectionError:
                click.echo(click.style(
                    'Unable to HEAD check {} in advance to see its '
                    'size. Proceeding anyway.'.format(
                        download_url,
                    ),
                    fg='yellow'
                ))
                content_length = None
        if (
            content_length is not None and
            content_length > max_size_bytes

        ):
            raise click.ClickException(
                '{} is {} but the max is {}'.format(
                    download_url,
                    (
                        'n/a' if content_length is None
                        else sizeof_fmt(content_length)
                    ),
                    sizeof_fmt(max_size_bytes),
                )
            )
        upload_by_download_url(
            url,
            auth_token,
            download_url,
            content_length,
            timeout=timeout,
        )
        return

    zips_dir = zips_dir or _default_zips_dir
    if not os.path.isdir(zips_dir):
        raise click.ClickException(
            'Directory {} does not exist'.format(zips_dir)
        )
    zips = glob.glob(os.path.join(zips_dir, '*.zip'))
    if not zips:
        raise click.ClickException(
            'Directory {} contains no .zip files'.format(zips_dir)
        )

    def locked(fn):
        return os.path.isfile(fn + '.locked')

    zips = [
        x for x in zips
        if os.stat(x).st_size < max_size_bytes and not locked(x)
    ]
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
        with open(zip_ + '.locked', 'w') as f:
            f.write('locked {}\n'.format(time.time()))
        try:
            successful = upload(zip_, url, auth_token, timeout=timeout)
            if not successful:
                upload_failures += 1
            if successful and delete_uploaded_file:
                click.style(
                    'Deleting zip file {}'.format(
                        zip_
                    )
                )
                os.remove(zip_)
        finally:
            if os.path.isfile(zip_ + '.locked'):
                os.remove(zip_ + '.locked')

    if upload_failures:
        raise click.ClickException(
            '{} files failed to upload'.format(upload_failures)
        )


if __name__ == '__main__':
    run()
