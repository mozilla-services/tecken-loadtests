#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: bin/print_locust_stats.py RUNNAME
#
# Prints the relevant stats from the .csv files that Locust generates for a
# given runname.

import contextlib

import click
from rich import box
from rich.console import Console
from rich.table import Table


def parse_val(val):
    if not val:
        return val

    with contextlib.suppress(ValueError):
        return int(val)

    with contextlib.suppress(ValueError):
        return float(val)

    return val


def format_val(val):
    if isinstance(val, int):
        return f"{val:,}"

    if isinstance(val, float):
        return f"{val:,.2f}"

    return str(val)


@click.command
@click.argument("runname")
@click.pass_context
def print_cmd(ctx, runname):
    console = Console(color_system=None)

    console.print(f"Runname: {runname}")

    with open(f"{runname}_stats.csv") as fp:
        lines = fp.readlines()

    columns = lines.pop(0).strip().split(",")
    all_data = []
    for line in lines:
        all_data.append(
            {key: parse_val(val) for key, val in zip(columns, line.strip().split(","))}
        )

    table = Table(box=box.ASCII, show_edge=False, safe_box=True, show_header=True)

    headers = ["Name", "Request Count", "Failure Count", "Requests/s", "Average Response Time", "50%", "95%"]
    table.add_column("Name", justify="left")
    table.add_column("Requests", justify="left")
    table.add_column("Failures", justify="left")
    table.add_column("Req/s", justify="left")
    table.add_column("Avg Time (ms)", justify="left")
    table.add_column("50% (ms)", justify="left")
    table.add_column("95% (ms)", justify="left")

    for item in all_data:
        if not item["Type"]:
            # Skip the "aggregated" line
            continue

        row = [format_val(item[header]) for header in headers]
        table.add_row(*row)

    console.print("")
    console.print("Requests:")
    console.print(table)

    with open(f"{runname}_failures.csv") as fp:
        lines = fp.readlines()

    if len(lines) == 1:
        console.print("")
        console.print("Failures: None")
    else:
        columns = lines.pop(0).strip().split(",")
        table = Table(box=box.ASCII, show_edge=False, safe_box=True, show_header=True)
        for col in columns:
            table.add_column(col, justify="left")

        for line in lines:
            table.add_row(*line.strip().split(","))

        console.print("")
        console.print("Failures:")
        console.print(table)


if __name__ == "__main__":
    print_cmd()
