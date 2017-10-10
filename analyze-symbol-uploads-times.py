"""
For a given site, download information about downloads to get an insight
into how the upload times are doing.
"""

import os
import statistics
from urllib.parse import urlparse

import dateutil.parser
import click
import requests


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return '%3.1f%s%s' % (num, unit, suffix)
        num /= 1024.0
    return '%.1f%s%s' % (num, 'Yi', suffix)


def format_seconds(s):
    return '{:.1f}s'.format(s)


def analyze(scheme, domain, auth_token, limit):
    base_url = scheme + '://' + domain
    uploads = get_uploads(base_url, auth_token, limit)
    print('Downloaded {} uploads'.format(len(uploads)))
    # from pprint import pprint
    upload_times = []
    for upload in uploads:
        if not upload['completed_at']:
            continue
        completed_file_uploads = [
            x for x in upload['file_uploads']
            if x['completed_at']
        ]
        if (
            not completed_file_uploads or
            len(completed_file_uploads) != len(upload['file_uploads'])
        ):
            # print("SKIP UPLOAD BECAUSE INCOMPLETE FILES")
            continue

        upload_completed_at = dateutil.parser.parse(upload['completed_at'])
        upload_created_at = dateutil.parser.parse(upload['created_at'])
        upload_diff = (upload_completed_at - upload_created_at).total_seconds()
        # print((created_at, completed_at, diff))
        # print((upload['size'], diff))
        # upload_times.append((
        #     diff,
        #     upload['size'],
        # ))
        file_upload_times = []
        for file_upload in completed_file_uploads:
            completed_at = dateutil.parser.parse(file_upload['completed_at'])
            created_at = dateutil.parser.parse(file_upload['created_at'])
            diff = (completed_at - created_at).total_seconds()
            file_upload_times.append((diff, file_upload['size']))
        upload_times.append((
            upload_created_at,
            upload_diff,
            upload['size'],
            file_upload_times
        ))

    def F(x, right=True):
        if not isinstance(x, str):
            x = str(x)
        return right and x.rjust(15) or x.center(15)

    def P(p):
        return F('{:.1f}%'.format(p))

    print('-' * 111)
    print(
        F('DATE', False),
        F('SIZE', False),
        F('TIME', False),
        F('FILES', False),
        F('SUM TIMES', False),
        F('WIN', False),
        F('SAVING', False),
    )

    all_wins = []
    all_savings = []
    for date, diff, size, file_times in upload_times:
        sum_files = sum(x[0] for x in file_times)
        win = 100 * sum_files / diff
        saving = sum_files - diff
        all_wins.append(win)
        all_savings.append(saving)
        print(
            F(date.strftime('%d %b %H:%M')),
            F(sizeof_fmt(size)),
            F(format_seconds(diff)),
            F(len(file_times)),
            F(format_seconds(sum_files)),
            P(win),
            F(format_seconds(saving)),
        )

    print('-' * 111)
    print(
        'AVERAGE WIN'.ljust(15),
        P(statistics.mean(all_wins)),
    )
    print(
        'MEDIAN WIN'.ljust(15),
        P(statistics.median(all_wins)),
    )
    print(
        'AVERAGE SAVINGS'.ljust(15),
        F(format_seconds(statistics.mean(all_savings))),
    )
    print(
        'MEDIAN SAVINGS'.ljust(15),
        F(format_seconds(statistics.median(all_savings))),
    )


def get_uploads(base_url, auth_token, limit):
    uploads = []
    page = 1
    while len(uploads) < limit:
        page_url = base_url + '/api/uploads/?page={}'.format(page)
        print(page_url)
        response = requests.get(page_url, headers={
            'auth-token': auth_token,
        })
        assert response.status_code == 200, response.status_code
        # total = response.json()['total']
        for upload in response.json()['uploads']:
            upload_url = base_url + '/api/uploads/upload/{}'.format(
                upload['id']
            )
            response = requests.get(upload_url, headers={
                'auth-token': auth_token,
            })
            assert response.status_code == 200, response.status_code
            upload['file_uploads'] = response.json()['upload']['file_uploads']
            uploads.append(upload)
        page += 1
        # print('compare', limit, total, len(uploads))
    return uploads


@click.command()
@click.option(
    '--limit',
    default=10,
    help='Number of uploads to look at (default 100)'
)
@click.option(
    '--domain',
    default='symbols.mozilla.org',
)
def run(
    limit,
    domain,
):
    try:
        auth_token = os.environ['AUTH_TOKEN']
    except KeyError:
        raise click.ClickException(
            'You have to set environment variable AUTH_TOKEN first.'
        )

    if '://' in domain:
        scheme = domain.split('://')[0]
        domain = urlparse(domain).netloc
    else:
        scheme = 'https'

    analyze(scheme, domain, auth_token, limit)
    return 0


if __name__ == '__main__':
    run()
