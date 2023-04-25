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
    "cache_lookups": {
        "count": 0,
        "hits": 0,
        "time": 0,
    },
    "downloads": {
        "count": 0,
        "time": 0,
        "size": 0,
        "size_per_module": {},
        "time_per_module": {},
        "fail_time_per_module": {},
    },
    "parse_sym": {
        "time": 0,
        "time_per_module": {},
        "fail_time_per_module": {},
    },
    "save_symcache": {
        "time": 0,
        "time_per_module": {},
    },
}


def sizeof_fmt(num, suffix="b"):
    for unit in ["", "k", "m", "g", "t", "p", "e", "z"]:
        if abs(num) < 1024.0:
            return f"{num:,.2f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:,.2f} Yi{suffix}"


def time_fmt(num):
    return f"{num:,.3f} s"


def number_fmt(num):
    return f"{num:,.3f}"


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
    """Takes out 0s and then returns avg, 50%, and stddev of a sequence"""
    r = [item for item in r if item]
    if len(r) == 0:
        return 0.0, 0.0, 0.0

    if len(r) == 1:
        return r[0], r[0], 0.0

    r = list(sorted(r))
    return (
        statistics.mean(r),
        r[len(r) // 2],
        statistics.stdev(r),
    )


def post_patiently(console, url, **kwargs):
    """Return delta, data for successful post"""
    attempts = kwargs.pop("attempts", 0)
    payload = kwargs["json"]
    try:
        start_time = time.time()
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

        return time.time() - start_time, resp.json()

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

    data = []

    files = [os.path.join(input_dir, x) for x in os.listdir(input_dir)]
    console.print(f"Got {len(files)} files")
    random.shuffle(files)

    if limit is not None:
        console.print(f"Limiting to {limit * batch_size} files")
        files = files[: limit * batch_size]

    now = datetime.datetime.now().strftime("%Y%m%d")
    logfile_path = f"symbolication-{now}.log"
    console.print(f"All verbose logging goes into: {logfile_path}")
    console.print()

    with open(logfile_path, "w") as logfile:
        try:
            bundle = []
            progress = Progress(expand=True, transient=True)
            with progress:
                for filename in progress.track(
                    files,
                    description="Processing ...",
                ):
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
                    print(f"PAYLOAD: {json.dumps(payload)}", file=logfile)

                    delta, resp = post_patiently(progress.console, url, json=payload)

                    print(f"RESPONSE: {json.dumps(resp)}", file=logfile)

                    debug = resp.get("debug", copy.deepcopy(EMPTY_DEBUG))
                    # progress.console.print(debug)
                    for module in (
                        debug.get("downloads", {}).get("size_per_module", {}).keys()
                    ):
                        module_size = debug["downloads"]["size_per_module"][module]
                        module_time = debug["downloads"]["time_per_module"][module]
                        speed = module_size / module_time / (1024 * 1024)
                        progress.print(
                            module,
                            f"{module_size:,}",
                            f"{module_time:,.2f} s",
                            f"{speed:,.2f} mb/s",
                        )

                    data_item = {
                        "time": delta,
                        "cache": {
                            "count": debug.get("cache_lookups", {}).get("count", 0),
                            "hits": debug.get("cache_lookups", {}).get("hits", 0),
                            "time": debug.get("cache_lookups", {}).get("time", 0.0),
                        },
                        "downloads": {
                            "count": debug.get("downloads", {}).get("count", 0),
                            # FIXME( the "time" and "size" fields are wrong in
                            # the debug output, so we sum them manually
                            "time": sum(
                                debug.get("downloads", {})
                                .get("time_per_module", {})
                                .values()
                                or [0]
                            ),
                            "size": sum(
                                debug.get("downloads", {})
                                .get("size_per_module", {})
                                .values()
                                or [0]
                            ),
                        },
                    }
                    data.append(data_item)

                    cache_data = data_item["cache"]
                    if cache_data["count"]:
                        _cache_lookups = (
                            f"{cache_data['count']} cache lookups "
                            + f"({cache_data['hits']}/{cache_data['count']}  {cache_data['time']:,.2f} s)"
                        )
                    else:
                        _cache_lookups = "no cache data"

                    download_data = data_item["downloads"]
                    if download_data["count"]:
                        _downloads = (
                            f"{download_data['count']} downloads "
                            + f"({download_data['size']:,} b  {download_data['time']:,.2f} s)"
                        )
                    else:
                        _downloads = "no download data"

                    # progress.console.print(debug)
                    delta_time = time_fmt(delta)

                    progress.console.print(
                        f"{_cache_lookups:<40}{_downloads:<40}{delta_time}"
                    )

        except KeyboardInterrupt:
            console.print("Keyboard interrupt...")

    # Display summary data and conclusion
    console.print("\n")
    if len(data) == (len(files) * batch_size):
        console.print(f"TOTAL {len(data)} JOBS DONE")
    else:
        console.print(f"TOTAL SO FAR {len(data)} JOBS DONE")

    one = copy.deepcopy(data[0])
    listify(one)
    for item in data[1:]:
        appendify(item, one)

    # console.print(one)

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
            else:
                value = value or 0.0
                average, median, stddev = _stats(value)
                if key.endswith("time"):
                    table.add_row(
                        prefix + key,
                        time_fmt(sum(value)),
                        time_fmt(average),
                        time_fmt(median),
                        number_fmt(stddev),
                    )

                elif key.endswith("size"):
                    table.add_row(
                        prefix + key,
                        sizeof_fmt(sum(value)),
                        sizeof_fmt(average),
                        sizeof_fmt(median),
                        number_fmt(stddev),
                    )

                else:
                    table.add_row(
                        prefix + key,
                        number_fmt(sum(value)),
                    )

    printify(one)

    console.print(table)

    console.print("\n")
    console.print("In conclusion...")
    if one["downloads"]["count"] and sum(one["downloads"]["time"]):
        downloads_speed = sizeof_fmt(
            sum(one["downloads"]["size"]) / sum(one["downloads"]["time"])
        )
        console.print(f"Final Average Download Speed:    {downloads_speed}/s")
    total_time_everything_else = (
        sum(one["time"]) - sum(one["downloads"]["time"]) - sum(one["cache"]["time"])
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
