#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Goes through symbolication log output for two symbolication sessions,
# looks at the debug sections in the symbolication responses, and generates a
# comparison table of download, parse, and save symfile timings between the two
# symbolication sessions for all the modules that were downloaded by both.
#
# This is helpful for comparing timings between two environments.
#
# To set the logs, see below.
#
# Usage: python compare_symbolication_logs.py

import json

from rich import box
from rich.console import Console
from rich.table import Table


LOG1 = "symbolication-gcp-20230418.log"
TITLE1 = "gcp prod 20230418"
LOG2 = "symbolication-gcp-prod-20230424.log"
TITLE2 = "gcp prod 20230424"


def load_data(fn):
    with open(fn, "r") as fp:
        return [
            json.loads(line.strip()[10:])
            for line in fp.readlines()
            if line.startswith("RESPONSE")
        ]


def sizeof_fmt(num, suffix="b"):
    for unit in ["", "k", "m", "g", "t", "p", "e", "z"]:
        if abs(num) < 1024.0:
            return f"{num:,.2f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:,.2f} Yi{suffix}"


def time_fmt(num):
    if not num:
        return ""
    if num > 30:
        return f"** [red]{num:,.2f} s[/red] **"
    return f"{num:,.2f} s"


def get_module_data(data):
    all_module_data = {}

    for item in data:
        debug_data = item.get("debug", {})

        all_modules = set()
        all_modules |= set(
            debug_data.get("downloads", {}).get("time_per_module", {}).keys()
        )
        all_modules |= set(
            debug_data.get("parse_sym", {}).get("time_per_module", {}).keys()
        )
        all_modules |= set(
            debug_data.get("save_symcache", {}).get("time_per_module", {}).keys()
        )

        for module in all_modules:
            module_data = all_module_data.get(module, {})

            download_time = (
                debug_data.get("downloads", {})
                .get("time_per_module", {})
                .get(module, None)
            )
            if download_time is not None:
                module_data.setdefault("download", []).append(download_time)
                module_data["size"] = debug_data["downloads"]["size_per_module"][module]

            parse_sym_time = (
                debug_data.get("parse_sym", {})
                .get("time_per_module", {})
                .get(module, None)
            )
            if parse_sym_time is not None:
                module_data.setdefault("parse_sym", []).append(parse_sym_time)

            save_symcache_time = (
                debug_data.get("save_symcache", {})
                .get("time_per_module", {})
                .get(module, None)
            )
            if save_symcache_time is not None:
                module_data.setdefault("save_symcache", []).append(save_symcache_time)

            all_module_data[module] = module_data

    return all_module_data


data_aws = load_data(LOG1)
module_aws = get_module_data(data_aws)

data_gcp = load_data(LOG2)
module_gcp = get_module_data(data_gcp)


console = Console()

all_rows = []

for key in set(module_aws.keys()) & set(module_gcp.keys()):
    # size
    if key in module_aws:
        size = module_aws[key]["size"]

    else:
        size = module_gcp[key]["size"]

    # size (int), module, size
    row = [size, key, sizeof_fmt(size)]

    # aws download
    row.append(
        ", ".join(
            [time_fmt(item) for item in module_aws.get(key, {}).get("download", [])]
        )
    )
    # gcp download
    row.append(
        ", ".join(
            [time_fmt(item) for item in module_gcp.get(key, {}).get("download", [])]
        )
    )

    # aws parse
    row.append(
        ", ".join(
            [time_fmt(item) for item in module_aws.get(key, {}).get("parse_sym", [])]
        )
    )
    # gcp parse
    row.append(
        ", ".join(
            [time_fmt(item) for item in module_gcp.get(key, {}).get("parse_sym", [])]
        )
    )

    # aws save
    row.append(
        ", ".join(
            [
                time_fmt(item)
                for item in module_aws.get(key, {}).get("save_symcache", [])
            ]
        )
    )
    # gcp save
    row.append(
        ", ".join(
            [
                time_fmt(item)
                for item in module_gcp.get(key, {}).get("save_symcache", [])
            ]
        )
    )

    all_rows.append(row)


table = Table(box=box.MARKDOWN, show_lines=False)
table.add_column("module")
table.add_column("size")

table.add_column(f"{TITLE1} download")
table.add_column(f"{TITLE2} download")

table.add_column(f"{TITLE1} parse")
table.add_column(f"{TITLE2} parse")

table.add_column(f"{TITLE1} save")
table.add_column(f"{TITLE2} save")

# Sort the rows by size, reversed
all_rows.sort(key=lambda item: item[0], reverse=True)
for row in all_rows:
    table.add_row(*row[1:])

console.print(table)
