# Molotov testing Tecken.

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Depends on reading the ./stacks/ directory,

./downloading/symbol-queries-groups.csv and ./downloading/socorro-missing.csv

"""

import csv
import os
import random
from glob import glob
from urllib.parse import urlencode

import molotov
from molotov.util import set_var, get_var


DEFAULT_URL_SERVER = "http://localhost:8050"


@molotov.global_setup()
def test_starts(args):
    """ This functions is called before anything starts.

    Notice that it's not a coroutine.
    """
    stacks_dir = "stacks"
    socorro_missing_csv = "downloading/socorro-missing.csv"
    symbol_queries_csv = "downloading/symbol-queries-groups.csv"
    # Populate the STACKS list with a list of paths to all stacks files
    set_var("url_server", os.getenv("URL_SERVER", DEFAULT_URL_SERVER))
    stacks = glob(os.path.join(stacks_dir, "*.json"))
    random.shuffle(stacks)
    set_var("stacks", stacks)

    # Populate ALL possible (and relevant URLs) for doing symbol downloads
    code_files_and_ids = {}
    with open(socorro_missing_csv) as f:
        reader = csv.reader(f)
        header = next(reader)
        _expect = ["debug_file", "debug_id", "code_file", "code_id"]
        assert header == _expect, header
        for row in reader:
            debug_file, debug_id, code_file, code_id = row
            code_files_and_ids[(debug_file, debug_id)] = (
                code_file,
                code_id,
            )

    with open(symbol_queries_csv) as f:
        reader = csv.reader(f)
        next(reader)  # header
        jobs_raw = list(reader)

    # This list of jobs will be predominately failed lookups (403 or 404
    # status codes). Let's balance that a bit so it's about 50%
    # that we expect to find too.
    jobs = []
    for job in jobs_raw:
        s3_uri = job[0]
        if "HTTP/1.1" in s3_uri:
            # A bad line in the CSV
            continue
        uri = "/".join(s3_uri.split("/")[-3:])
        try:
            symbol, debugid, filename = uri.split("/")
        except ValueError:
            continue
        key = (symbol, debugid)
        if key in code_files_and_ids:
            code_file, code_id = code_files_and_ids[key]
            uri += "?{}".format(urlencode({
                "code_file": code_file,
                "code_id": code_id,
            }))
        status_code = int(job[1])
        if status_code == 403:
            # When a line in the CSV says 403, it"s just because it"s
            # an attempt to open a URL on a private bucket.
            # In Tecken, it doesn"t do that distinction.
            status_code = 404
        jobs.append((uri, status_code))

    found_jobs = [x for x in jobs if x[1] == 200]
    notfound_jobs = [x for x in jobs if x[1] != 200]
    assert len(found_jobs) < len(notfound_jobs)
    SYMBOLS = found_jobs + notfound_jobs[:len(found_jobs)]
    random.shuffle(SYMBOLS)
    set_var("symbols", SYMBOLS)


@molotov.setup()
async def worker_starts(worker_id, args):
    """This function is called once per worker.

    If it returns a mapping, it will be used with all requests.

    You can add things like Authorization headers for instance,
    by setting a "headers" key.
    """
    headers = {
        # Empty for now
    }
    return {"headers": headers}


@molotov.scenario(40)
async def scenario_symbolication(session):
    headers = {"Content-Type": "application/json"}

    with open(get_var("stacks").pop()) as f:
        url = get_var("url_server") + "/symbolicate/v5"
        async with session.post(url, data=f, headers=headers) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "knownModules" in data
            assert "symbolicatedStacks" in data
