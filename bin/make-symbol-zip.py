#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Generates large symbol.zip files for upload testing based on looking at logs
in https://crash-stats.mozilla.com/api/UploadedSymbols/ .

However, since all files in there are public, a bunch of these queries
have already been made and saved into ./symbols-uploaded/.
"""

import tempfile
import os
import random
import time
import zipfile
import glob
import gzip
import json
import re
import multiprocessing
import concurrent.futures
from urllib.parse import urlparse

import click
import deco
import requests


SYMBOLS_DIR = (
    "https://s3-us-west-2.amazonaws.com/org.mozilla.crash-stats.symbols-public/"
)

ZIPS_DIR = "upload-zips"


compression = zipfile.ZIP_DEFLATED


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)


def seconds_fmt(t):
    return "{:.2f}s".format(t)


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


def time_fmt(secs):
    return "{:.2f}s".format(secs)


@deco.concurrent
def download(uri, save_dir, store):
    store[uri] = _download(uri, save_dir)


def _download(uri, save_dir):
    url = SYMBOLS_DIR + uri.split(",", 1)[1]
    t0 = time.time()
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(
            "Got {} trying to download {}".format(response.status_code, url)
        )
    path = uri.split(",", 1)[1].replace("v1/", "")
    dirname = os.path.join(save_dir, os.path.dirname(path))
    os.makedirs(dirname, exist_ok=True)
    basename = os.path.basename(path)
    fullpath = os.path.join(dirname, basename)
    with open(fullpath, "wb") as f:
        f.write(response.content)
    t1 = time.time()
    size = int(response.headers["Content-Length"])
    print(
        response.status_code,
        sizeof_fmt(size).ljust(8),
        seconds_fmt(t1 - t0).ljust(8),
        (sizeof_fmt(size / (t1 - t0)) + "/s").ljust(8),
        urlparse(url).path.split("/v1")[1],
    )
    return fullpath, t1 - t0, int(response.headers["Content-Length"])


def _get_index(save_dir, days=0, max_size=None, silent=False):
    # Pick a random file from the ./symbols-uploaded/ directory
    symbols_uploaded_dir = "symbols-uploaded"
    symbols_uploaded_file = random.choice(
        glob.glob(os.path.join(symbols_uploaded_dir, "*.json.gz"))
    )
    print("SYMBOLS_UPLOADED_FILE:", symbols_uploaded_file)
    with gzip.open(symbols_uploaded_file, "rb") as f:
        uploaded = json.loads(f.read().decode("utf-8"))
    all_uploads = uploaded["hits"]
    possible = {}
    for i, bundle in enumerate(all_uploads):
        if max_size is not None and bundle["size"] > max_size:
            continue
        wouldbe_name = _make_filepath(save_dir, bundle)
        saved_already = os.path.isfile(wouldbe_name)
        if not silent:
            print(
                str(i + 1).ljust(4),
                bundle["date"].ljust(37),
                sizeof_fmt(bundle["size"]).ljust(10),
                "saved already" if saved_already else "",
            )
        if not saved_already:
            possible[i] = (bundle["date"], bundle["size"])

    if not possible:
        raise Exception("No possible zip files")
    if silent:
        preferred = None
    else:
        preferred = input("Which one? [blank for random]: ")
    if not preferred:
        preferred = random.choice(list(possible.keys()))
    else:
        preferred = int(preferred) - 1
    print(
        "Picking {} ({})".format(
            possible[preferred][0], sizeof_fmt(possible[preferred][1])
        )
    )
    print()
    return all_uploads[preferred]


@deco.synchronized
def download_all(urls, save_dir):
    print("Downloading into", save_dir)
    downloaded = {x: False for x in urls}
    for url in urls:
        if url.endswith("/"):
            print("Bad URL (ignoring) {}".format(url))
        else:
            download(url, save_dir, downloaded)
    return downloaded


def download_all_threads(urls, save_dir):
    print("Downloading into", save_dir)
    futures = {}
    downloaded = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        for url in urls:
            if url.endswith("/"):
                print("Bad URL (ignoring) {}".format(url))
                continue
            futures[executor.submit(_download, url, save_dir)] = url
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            downloaded[url] = future.result()
    return downloaded


def _make_filepath(save_dir, bundle):
    date = bundle["date"].split(".")[0].replace(":", "_")
    return os.path.join(save_dir, "symbols-{date}.zip".format(date=date))


@click.command()
@click.option(
    "--save-dir", help="Where all .zip files get saved (default {})".format(ZIPS_DIR)
)
@click.option(
    "--max-size",
    help="Max size of files to upload (default is no limit)",
)
@click.option(
    "--silent",
    help="Will not prompt for an input and use random choice if need be",
    is_flag=True,
)
@click.option(
    "--use-threads",
    help=("Use concurrent.futures.ThreadPoolExecutor instead of multiprocessing"),
    is_flag=True,
)
def run(save_dir=None, max_size=None, silent=False, use_threads=False):
    if max_size:
        max_size = parse_file_size(max_size)
        print(
            "Max. size filter:",
            sizeof_fmt(max_size),
        )
    save_dir = save_dir or ZIPS_DIR
    if not os.path.isdir(save_dir):
        os.makedirs(save_dir, exist_ok=True)
    bundle = _get_index(save_dir, max_size=max_size, silent=silent)
    all_symbol_urls = []
    all_symbol_urls.extend(bundle["content"].get("added", []))
    all_symbol_urls.extend(bundle["content"].get("existed", []))
    print(len(all_symbol_urls), "URLs to download")
    with tempfile.TemporaryDirectory(prefix="symbols") as tmpdirname:
        t0 = time.time()
        if use_threads:
            downloaded = download_all_threads(all_symbol_urls, tmpdirname)
        else:
            downloaded = download_all(all_symbol_urls, tmpdirname)
        if isinstance(downloaded, bool):
            print("all_symbol_urls", all_symbol_urls)
            raise Exception(
                "The downloaded dict became a boolean! ({!r})".format(
                    downloaded,
                )
            )
        t1 = time.time()
        save_filepath = _make_filepath(save_dir, bundle)
        total_time_took = 0.0
        total_size = 0
        sizes = []
        times = []

        with zipfile.ZipFile(save_filepath, mode="w") as zf:
            for uri, download_result in downloaded.items():
                if not download_result:
                    print("Nothing downloaded for {}".format(uri))
                    continue
                fullpath, time_took, size = download_result
                total_time_took += time_took
                times.append(time_took)
                total_size += size
                sizes.append(size)
                if fullpath:
                    path = uri.split(",")[1].replace("v1/", "")
                    assert os.path.isfile(fullpath)
                    zf.write(
                        fullpath,
                        arcname=path,
                        compress_type=zipfile.ZIP_DEFLATED,
                    )

        print()
        P = 30
        print("TO".ljust(P), save_filepath)
        print(
            "# CPUS:".ljust(P),
            multiprocessing.cpu_count(),
        )
        print(
            "Sum time took:".ljust(P),
            time_fmt(total_time_took).ljust(P),
            "Download speed:".ljust(P),
            sizeof_fmt(sum(sizes) / sum(times)) + "/s",
        )
        download_speed = sum(sizes) / (t1 - t0)
        print(
            "Total time took:".ljust(P),
            time_fmt(t1 - t0).ljust(P),
            "Download speed:".ljust(P),
            sizeof_fmt(download_speed) + "/s",
        )
        with open(".downloadspeeds.log", "a") as f:
            f.write(
                "{}\t{}\n".format(
                    download_speed, use_threads and "threads" or "multiprocessing"
                )
            )
        print(
            "Total size (files):".ljust(P),
            total_size,
            "({})".format(sizeof_fmt(total_size)),
        )
        print(
            "Total size:".ljust(P),
            os.stat(save_filepath).st_size,
            "({})".format(sizeof_fmt(os.stat(save_filepath).st_size)),
        )
        print(
            "Bundle size:".ljust(P),
            bundle["size"],
            "({})".format(sizeof_fmt(bundle["size"])),
        )

    return 0


if __name__ == "__main__":
    run()
