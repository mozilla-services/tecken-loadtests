#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
List recently generated symbols ZIP files in taskcluster. You can
use these to do "upload by download url".
"""

import re

import click
import requests


INDEX = "https://index.taskcluster.net/v1/"
QUEUE = "https://queue.taskcluster.net/v1/"


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)


def index_namespaces(namespace, limit=1000):
    r = requests.post(INDEX + "namespaces/" + namespace, json={"limit": limit})
    for n in r.json()["namespaces"]:
        yield n["namespace"]


def parse_file_size(s):
    parsed = re.findall(r"([\d\.]+)([gmbk]+)", s)
    if not parsed:
        number = s
        unit = "b"
    else:
        number, unit = parsed[0]
    number = float(number)
    unit = unit.lower()

    if unit == "b":
        pass
    elif unit in ("k", "kb"):
        number *= 1024
    elif unit in ("m", "mb"):
        number *= 1024 * 1024
    elif unit in ("g", "gb"):
        number *= 1024 * 1024 * 1024
    else:
        raise NotImplementedError(unit)
    return int(number)


def index_tasks(namespace, limit=1000):
    r = requests.post(INDEX + "tasks/" + namespace, json={"limit": limit})
    for t in r.json()["tasks"]:
        yield t["taskId"]


def tasks_by_changeset(revisions_limit):
    namespaces_generator = index_namespaces(
        "gecko.v2.mozilla-central.nightly.revision", revisions_limit
    )
    for n in namespaces_generator:
        for t in index_tasks(n + ".firefox"):
            yield t


def list_artifacts(task_id):
    r = requests.get(QUEUE + "task/%s/artifacts" % task_id)
    if r.status_code != 200:
        return []
    return [a["name"] for a in r.json()["artifacts"]]


def get_symbols_urls():
    for t in tasks_by_changeset(5):
        artifacts = list_artifacts(t)
        full = [a for a in artifacts if a.endswith(".crashreporter-symbols-full.zip")]
        if full:
            yield QUEUE + "task/%s/artifacts/%s" % (t, full[0])
        else:
            small = [a for a in artifacts if a.endswith(".crashreporter-symbols.zip")]
            if small:
                yield QUEUE + "task/%s/artifacts/%s" % (t, small[0])


def get_content_length(url):
    response = requests.head(url)
    if response.status_code > 300 and response.status_code < 400:
        return get_content_length(response.headers["location"])
    return int(response.headers["content-length"])


@click.command()
@click.option(
    "--number",
    default=5,
    type=int,
    help="number of urls to print out; don't do more than 100",
)
@click.option("--max-size", default="1000mb", help="max size for urls to print out")
@click.option("--url-only/--no-url-only", default=False, help="print just the url")
def run(number, max_size, url_only):
    max_size_bytes = parse_file_size(max_size)

    if number > 100:
        raise click.BadParameter("number should not be greater than 100")

    for url in get_symbols_urls():
        if number <= 0:
            break

        size = get_content_length(url)
        if size > max_size_bytes:
            continue

        if url_only:
            print(url)
        else:
            print(sizeof_fmt(size).ljust(10), url)
        number -= 1


if __name__ == "__main__":
    run()
