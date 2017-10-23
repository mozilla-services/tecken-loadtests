#!/usr/bin/env python

from __future__ import print_function

import itertools
import requests

INDEX = 'https://index.taskcluster.net/v1/'
QUEUE = 'https://queue.taskcluster.net/v1/'


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return '%3.1f%s%s' % (num, unit, suffix)
        num /= 1024.0
    return '%.1f%s%s' % (num, 'Yi', suffix)


def index_namespaces(namespace, limit=1000):
    r = requests.post(INDEX + 'namespaces/' + namespace,
                      json={'limit': limit})
    for n in r.json()['namespaces']:
        yield n['namespace']


def index_tasks(namespace, limit=1000):
    r = requests.post(INDEX + 'tasks/' + namespace,
                      json={'limit': limit})
    for t in r.json()['tasks']:
        yield t['taskId']


def tasks_by_changeset(revisions_limit):
    namespaces_generator = index_namespaces(
        'gecko.v2.mozilla-central.nightly.revision',
        revisions_limit
    )
    for n in namespaces_generator:
        for t in index_tasks(n + '.firefox'):
            yield t


def list_artifacts(task_id):
    r = requests.get(QUEUE + 'task/%s/artifacts' % task_id)
    if r.status_code != 200:
        return []
    return [a['name'] for a in r.json()['artifacts']]


def get_symbols_urls():
    for t in tasks_by_changeset(5):
        artifacts = list_artifacts(t)
        full = [
            a for a in artifacts
            if a.endswith('.crashreporter-symbols-full.zip')
        ]
        if full:
            yield QUEUE + 'task/%s/artifacts/%s' % (t, full[0])
        else:
            small = [
                a for a in artifacts
                if a.endswith('.crashreporter-symbols.zip')
            ]
            if small:
                yield QUEUE + 'task/%s/artifacts/%s' % (t, small[0])


def get_content_length(url):
    response = requests.head(url)
    if response.status_code > 300 and response.status_code < 400:
        return get_content_length(response.headers['location'])
    return int(response.headers['content-length'])


if __name__ == '__main__':
    import sys
    try:
        n = int(sys.argv[1])
    except IndexError:
        n = 10
    assert n > 0 and n < 100, n
    for url in itertools.islice(get_symbols_urls(), n):
        size = get_content_length(url)
        print(
            sizeof_fmt(size).ljust(10),
            url,
        )
