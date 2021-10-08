# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import copy
import datetime
import json
import os
import random
import shutil
import tempfile
import time
from urllib.parse import urlparse

import click
import requests
from requests.exceptions import ConnectionError


EMPTY_DEBUG = {
    "time": 0,
    "modules": {
        "stacks_per_module": None,
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


def clear_line():
    """Clears the line in the terminal"""
    width = shutil.get_terminal_size()[0]
    click.echo((" " * width) + "\r", nl=False)


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


def wc_dir(fd):
    return len(os.listdir(fd))
    # with open(fd) as f:
    #     return f.read().count('\n')


def listify(d):
    for key, value in d.items():
        if isinstance(value, dict):
            listify(value)
        else:
            d[key] = [value]


def appendify(source, dest):
    for key, value in source.items():
        if isinstance(value, dict):
            appendify(value, dest[key])
        else:
            dest[key].append(value)


def printify(objects, p=30, n=10, prefix=""):
    for key in sorted(objects):
        value = objects[key]
        if isinstance(value, dict):
            printify(value, p=p, n=n, prefix=prefix + key + ".")
        else:
            formatter = number_fmt
            if key == "size":
                formatter = sizeof_fmt
            elif key.endswith("time"):
                formatter = time_fmt
            median, average, stddev = _stats(value)
            click.echo(
                (prefix + key).ljust(p)
                + formatter(sum(value)).rjust(n)
                + formatter(average).rjust(n)
                + formatter(median).rjust(n)
                + formatter(stddev).rjust(n)
            )


def _stats(r):
    # returns the median, average and standard deviation of a sequence
    tot = sum(r)
    avg = tot / len(r)
    sdsq = sum([(i - avg) ** 2 for i in r])
    s = list(r)
    s.sort()
    return s[len(s) // 2], avg, (sdsq / (len(r) - 1 or 1)) ** 0.5


def post_patiently(url, **kwargs):
    attempts = kwargs.pop("attempts", 0)
    payload = kwargs["json"]
    try:
        t0 = time.time()
        options = {
            "headers": {
                "Debug": "true",
            },
        }
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.netloc == "prod.tecken.dev":
            options["verify"] = False
        resp = requests.post(url, json=payload, **options)
        if resp.status_code == 502 and "localhost:8000" in url:
            click.echo("")
            click.echo(
                "Got HTTP 502 which is probably a Django server restart; retrying"
            )
            raise ConnectionError()
        if resp.status_code != 200:
            click.echo("PAYLOAD:", json.dumps(payload))
            click.echo("Got HTTP {}".format(resp.status_code))
            click.echo("CONTENT: {}".format(resp.content))
            raise ConnectionError()
        data = resp.json()
        t1 = time.time()
        return (t1, t0), data
    except ConnectionError:
        if attempts > 3:
            raise
        time.sleep(2)
        return post_patiently(url, attempts=attempts + 1, **kwargs)


@click.command()
@click.option(
    "--limit",
    "-l",
    default=None,
    type=int,
    help="Max. number of iterations (default infinity)",
)
@click.option(
    "--batch-size",
    "-b",
    default=1,
    type=int,
    help="Number of jobs to bundle per symbolication",
)
@click.argument("input_dir")
@click.argument("url")
def run(input_dir, url, limit=None, batch_size=1):
    url_parsed = urlparse(url)
    if not url_parsed.path or url_parsed.path == "/":
        if not url_parsed.path:
            url += "/"
        url += "symbolicate/v5"

    if not urlparse(url).path.endswith("/v5"):
        raise click.BadParameter("symbolication.py only supports v5")

    files_count = wc_dir(input_dir)
    click.echo(f"{files_count:,} FILES")
    click.echo()
    all_debugs = []

    def print_total_debugs(finished):
        click.echo("\n")
        if finished:
            click.echo(f"TOTAL {len(all_debugs)} JOBS DONE")
        else:
            click.echo(f"TOTAL SO FAR {len(all_debugs)} JOBS DONE")
        one = copy.deepcopy(all_debugs[0])
        listify(one)
        for debug in all_debugs:
            appendify(debug, one)

        P = 23
        N = 15
        click.echo(
            "KEY".ljust(P)
            + "SUM".rjust(N)
            + "AVG".rjust(N)
            + "MEDIAN".rjust(N)
            + "STD-DEV".rjust(N)
        )
        printify(one, P, N)

        click.echo("\n")
        click.echo("IN CONCLUSION...")
        if one["downloads"]["count"] and sum(one["downloads"]["time"]):
            click.echo(
                "Final Average Download Speed".ljust(P)
                + "{}/s".format(
                    sizeof_fmt(
                        sum(one["downloads"]["size"]) / sum(one["downloads"]["time"])
                    )
                )
            )
        total_time_everything_else = (
            sum(one["time"])
            - sum(one["downloads"]["time"])
            - sum(one["cache_lookups"]["time"])
        )
        click.echo(
            "Total time NOT downloading or querying cache  "
            + time_fmt(total_time_everything_else)
        )
        click.echo(
            "Average time NOT downloading or querying cache"
            + time_fmt(total_time_everything_else / len(one["time"]))
        )

    times = []

    def total_duration():
        if not times:
            return "na"
        seconds = time.time() - times[0]
        if seconds < 100:
            return "{:.1f} seconds".format(seconds)
        else:
            return "{:.1f} minutes".format(seconds / 60)

    def speed_per_second(last=10):
        if not times:
            return "na"
        if len(times) > last:
            t = time.time() - times[-last]
            L = last
        else:
            t = time.time() - times[0]
            L = len(times)
        return "{:.1f}".format(L / t)

    def speed_per_minute(last=10):
        if not times:
            return "na"
        if len(times) > last:
            t = time.time() - times[-last]
            L = last
        else:
            t = time.time() - times[0]
            L = len(times)
        return "{:.1f}".format(L * 60 / t)

    files = [os.path.join(input_dir, x) for x in os.listdir(input_dir)]
    click.echo(f"Got {len(files)} files")
    random.shuffle(files)

    now = datetime.datetime.now().strftime("%Y%m%d")
    logfile_path = os.path.join(tempfile.gettempdir(), "symbolication-" + now + ".log")
    click.echo(f"All verbose logging goes into: {logfile_path}")
    click.echo()
    try:
        bundle = []
        for i, filename in enumerate(files):
            with open(filename) as f, open(logfile_path, "a") as logfile:
                payload = json.loads(f.read())
                payload.pop("version", None)
                bundle.append(payload)
                if len(bundle) < batch_size:
                    continue
                else:
                    payload = {"jobs": list(bundle)}
                    bundle = []

                print("FILE: %s" % filename, file=logfile)
                print("PAYLOAD (as JSON)", file=logfile)
                print("-" * 79, file=logfile)
                print(json.dumps(payload), file=logfile)

                (t1, t0), r = post_patiently(url, json=payload)
                # print(r['knownModules'])
                # t0 = time.time()
                # req = requests.post(url, json=payload)
                # r = req.json()
                # t1 = time.time()
                # print(r)
                print(file=logfile)
                print("RESPONSE (as JSON)", file=logfile)
                print("-" * 79, file=logfile)
                print(json.dumps(r), file=logfile)
                print("-" * 79, file=logfile)
                # memory_map = set()
                # for i, job in enumerate(payload['jobs']):
                #     result = r['results'][i]
                #     print("JOB")
                #     print(job)
                #     print("RESULT")
                #     print(result)
                #     for x, frames in enumerate(result['stacks']):
                #         for y, frame in enumerate(frames):
                #             stack = job['stacks'][x][y]
                #             print("STACK", stack)
                #             module_index = stack[0]

                #             print("FRAMES", frame)
                #             raise Exception
                #     raise Exception
                #     for j, combo in enumerate(job['memoryMap']):

                #         print(
                #             combo,
                #             '-->',
                #             r['results'][i]['knownModules'][j],
                #             file=logfile
                #         )
                #     for combo in job['memoryMap']:
                #         memory_map.add(tuple(combo))
                # memory_map = list(memory_map)
                # x=r['results'][0]
                # x.pop('debug')
                # print(x)
                # known_modules = {}
                # XXX https://bugzilla.mozilla.org/show_bug.cgi?id=1434350

                # for j, combo in enumerate(payload['memoryMap']):
                #     print(combo, '-->', r['knownModules'][j], file=logfile)
                # for combo in memory_map:
                #     print("COMBO", combo)
                #     print(combo, '-->', r['knownModules'][j], file=logfile)
                # print('=' * 79, file=logfile)
                # print(file=logfile)
                times.append(t0)
                debug_downloads_counts = []
                debug_downloads_times = []
                debug_downloads_sizes = []
                cache_lookups_counts = []
                cache_lookups_times = []
                modules_counts = []
                downloads_counts = []
                for result in r["results"]:
                    # FIXME(willkg): Eliot doesn't support the Debug header,
                    # yet. Once it does, we can fix this.
                    debug = result.get("debug", EMPTY_DEBUG)
                    if "stacks_per_module" in debug["modules"]:
                        debug["modules"].pop("stacks_per_module")
                    debug_downloads_counts.append(debug["downloads"]["count"])
                    debug_downloads_times.append(debug["downloads"]["time"])
                    debug_downloads_sizes.append(debug["downloads"]["size"])
                    cache_lookups_counts.append(debug["cache_lookups"]["count"])
                    cache_lookups_times.append(debug["cache_lookups"]["time"])
                    modules_counts.append(debug["modules"]["count"])
                    downloads_counts.append(debug["downloads"]["count"])
                    # debug['loader_time'] = t1 - t0
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

                clear_line()
                click.echo(f"{_downloads.ljust(35)}{_cache_lookups}")

                out = " {} of {} -- {} requests/minute ({} req/s) ({}) ".format(
                    format(i + 1, ","),
                    format(files_count, ","),
                    speed_per_minute(),
                    speed_per_second(),
                    total_duration(),
                ).center(80, "=")
                click.echo(out, nl=False)
                click.echo("\r" * len(out), nl=False)
                time.sleep(0.05)
            if limit is not None and i == limit - 1:
                break
    except KeyboardInterrupt:
        print_total_debugs(False)
        return

    print_total_debugs(True)


if __name__ == "__main__":
    run()
