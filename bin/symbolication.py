#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: bin/symbolication.py STACKSDIR HOST/URL

import copy
import datetime
import json
import os
import random
import statistics
import tempfile
import time
from urllib.parse import urlparse

import click
import requests
from requests.exceptions import ConnectionError
from rich.console import Console
from rich.progress import Progress
from rich.table import Table


TIMEOUT = 120

EMPTY_DEBUG = {
    "time": 0,
    "modules": {
        "stacks_per_module": 0,
        "count": 0,
    },
    "downloads": {
        "count": 0,
        "time": 0,
        "size": 0,
    },
    "cache_lookups": {
        "count": 0,
        "time": 0,
    },
}


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)


def number_fmt(x):
    if isinstance(x, int):
        return str(x)
    return "{:.2f}".format(x)


def time_fmt(x):
    return "{:.3f}s".format(x)


def listify(d):
    for key, value in d.items():
        if isinstance(value, dict):
            listify(value)
        else:
            d[key] = [value]


def appendify(source, dest):
    for key, value in source.items():
        if isinstance(value, dict):
            appendify(value, dest.setdefault(key, {}))
        else:
            dest.setdefault(key, []).append(value)


def _stats(r):
    """Return avg, 50%, and stddev of a sequence"""
    r = list(sorted(r))
    return (
        statistics.mean(r),
        r[len(r) // 2],
        statistics.stdev(r),
    )


def post_patiently(console, url, **kwargs):
    attempts = kwargs.pop("attempts", 0)
    payload = kwargs["json"]
    try:
        t0 = time.time()
        options = {
            "headers": {"Debug": "true"},
            "timeout": TIMEOUT,
        }
        resp = requests.post(url, json=payload, **options)
        if resp.status_code != 200:
            console.print(f"PAYLOAD: {json.dumps(payload)}")
            console.print(f"Got HTTP {resp.status_code}")
            console.print(f"CONTENT: {resp.content}")
            raise ConnectionError()
        data = resp.json()
        t1 = time.time()
        return (t1, t0), data
    except ConnectionError:
        if attempts > 3:
            raise
        time.sleep(2)
        return post_patiently(console, url, attempts=attempts + 1, **kwargs)


@click.command()
@click.option(
    "--limit",
    "-l",
    default=None,
    type=int,
    help="Max. number of iterations; default=infinite",
)
@click.option(
    "--batch-size",
    "-b",
    default=1,
    type=int,
    help="Number of jobs to bundle per symbolication; default=1",
)
@click.argument("input_dir")
@click.argument("url")
def run(input_dir, url, limit=None, batch_size=1):
    console = Console()

    url_parsed = urlparse(url)
    if not url_parsed.path or url_parsed.path == "/":
        if not url_parsed.path:
            url += "/"
        url += "symbolicate/v5"

    if not urlparse(url).path.endswith("/v5"):
        raise click.BadParameter("symbolication.py only supports v5")

    all_debugs = []

    times = []

    files = [os.path.join(input_dir, x) for x in os.listdir(input_dir)]
    console.print(f"Got {len(files)} files")
    random.shuffle(files)

    if limit is not None:
        console.print(f"Limiting to {limit * batch_size} files")
        files = files[:limit * batch_size]

    now = datetime.datetime.now().strftime("%Y%m%d")
    logfile_path = os.path.join(tempfile.gettempdir(), "symbolication-" + now + ".log")
    console.print(f"All verbose logging goes into: {logfile_path}")
    console.print()

    with open(logfile_path, "a") as logfile:
        try:
            bundle = []
            progress = Progress(expand=True, transient=True)
            with progress:
                for filename in progress.track(files, description="Processing ...", ):
                    with open(filename) as f:
                        payload = json.loads(f.read())
                        payload.pop("version", None)
                        bundle.append(payload)
                        if len(bundle) < batch_size:
                            continue
                        else:
                            payload = {"jobs": list(bundle)}
                            bundle = []

                    print(f"FILE: {filename}", file=logfile)
                    print("PAYLOAD (as JSON)", file=logfile)
                    print("-" * 79, file=logfile)
                    print(json.dumps(payload), file=logfile)

                    (t1, t0), r = post_patiently(progress.console, url, json=payload)

                    print(file=logfile)
                    print("RESPONSE (as JSON)", file=logfile)
                    print("-" * 79, file=logfile)
                    print(json.dumps(r), file=logfile)
                    print("-" * 79, file=logfile)

                    times.append(t0)
                    debug_downloads_counts = []
                    debug_downloads_times = []
                    debug_downloads_sizes = []
                    cache_lookups_counts = []
                    cache_lookups_times = []
                    modules_counts = []
                    downloads_counts = []

                    debug = r.get("debug", copy.deepcopy(EMPTY_DEBUG))
                    if "stacks_per_module" in debug["modules"]:
                        debug["modules"].pop("stacks_per_module")
                    debug_downloads_counts.append(debug["downloads"]["count"])
                    debug_downloads_times.append(debug["downloads"]["time"])
                    debug_downloads_sizes.append(debug["downloads"]["size"])
                    cache_lookups_counts.append(debug["cache_lookups"]["count"])
                    cache_lookups_times.append(debug["cache_lookups"]["time"])
                    modules_counts.append(debug["modules"]["count"])
                    downloads_counts.append(debug["downloads"]["count"])
                    all_debugs.append(debug)

                    if sum(debug_downloads_counts):
                        _downloads = "{} downloads ({}, {})".format(
                            sum(debug_downloads_counts),
                            time_fmt(sum(debug_downloads_times)),
                            sizeof_fmt(sum(debug_downloads_sizes)),
                        )
                    else:
                        _downloads = "no download data"

                    if sum(cache_lookups_counts):
                        _cache_lookups = "{} ({}) cache lookup{} ({} -- {}/lookup)".format(
                            sum(cache_lookups_counts),
                            (sum(modules_counts) - sum(downloads_counts)),
                            sum(cache_lookups_counts) > 1 and "s" or "",
                            time_fmt(sum(cache_lookups_times)),
                            time_fmt(sum(cache_lookups_times) / sum(cache_lookups_counts)),
                        )
                    else:
                        _cache_lookups = "no cache data"

                    progress.console.print(f"{_downloads.ljust(35)}{_cache_lookups}")

        except KeyboardInterrupt:
            console.print("Keyboard interrupt...")

    # Display summary data and conclusion
    console.print("\n")
    if len(all_debugs) == (len(files) * batch_size):
        console.print(f"TOTAL {len(all_debugs)} JOBS DONE")
    else:
        console.print(f"TOTAL SO FAR {len(all_debugs)} JOBS DONE")

    one = copy.deepcopy(all_debugs[0])
    listify(one)
    for debug in all_debugs:
        appendify(debug, one)

    table = Table()
    table.add_column("Key", justify="left")
    table.add_column("Sum", justify="right")
    table.add_column("Avg", justify="right")
    table.add_column("50%", justify="right")
    table.add_column("StdDev", justify="right")

    def printify(objects, p=30, n=10, prefix=""):
        for key in sorted(objects):
            value = objects.get(key, None)
            if isinstance(value, dict):
                printify(value, p=p, n=n, prefix=prefix + key + ".")
                return

            value = value or 0.0
            average, median, stddev = _stats(value)
            if key.endswith("time"):
                table.add_row(
                    prefix + key,
                    f"{sum(value):.2f}s",
                    f"{average:.2f}s",
                    f"{median:.2f}s",
                    f"{stddev:.2f}",
                )

            else:
                table.add_row(
                    prefix + key,
                    f"{sum(value):.2f}",
                )

    printify(one)

    console.print(table)

    console.print("\n")
    console.print("IN CONCLUSION...")
    if one["downloads"]["count"] and sum(one["downloads"]["time"]):
        downloads_speed = sizeof_fmt(
            sum(one["downloads"]["size"]) / sum(one["downloads"]["time"])
        )
        console.print(f"Final Average Download Speed:    {downloads_speed}/s")
    total_time_everything_else = (
        sum(one["time"])
        - sum(one["downloads"]["time"])
        - sum(one["cache_lookups"]["time"])
    )
    console.print(
        "Total time NOT downloading or querying cache:    "
        + time_fmt(total_time_everything_else)
    )
    console.print(
        "Average time NOT downloading or querying cache:  "
        + time_fmt(total_time_everything_else / len(one["time"]))
    )


if __name__ == "__main__":
    run()
