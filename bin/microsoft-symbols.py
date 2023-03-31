#!/usr/bin/env python

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
How the found-on-msdl.log was created.
First go to:
https://tools.taskcluster.net/index/project.socorro.fetch-win32-symbols/project.socorro.fetch-win32-symbols
Click on one of the dates (recent better)
Click on the TaskId (upper right hand corner) after having clicked
on a date.
Click on "View raw log" and copy all of its content into /tmp/tc.log
Then run this code (But note! this requires that the view, in real-time,
tries to do a Microsoft lookup):

    import requests
    import re
    all=set()
    with open('/tmp/tc.log') as f:

        for line in f:
            found = re.findall('(\w+\.pdb/[0-9A-F]+),', line)
            if found:
                all.add(found[0])
            # x= line.split('v1/')[1]
            # if '.pdb' in x and x.endswith('.pd_'):
            #     print(x)
            #     print(requests.get('http://localhost:8000/' + x).status_code)
            #     print()

    all = list(all)
    import random
    for name in random.sample(all, 10000):
        a, _ = name.split('/')
        uri = name + '/' + a.replace('.pdb', '.pd_')
        print(uri)
        if requests.get('http://localhost:8000/' + uri).status_code != 404:
            print("*******************************")
            print("YAY!!")
            print('\n')


"""

import random
import os

import click
import requests


def _load(search):
    here = os.path.dirname(__file__)
    uris = set()
    with open(os.path.join(here, "found-on-msdl.log")) as f:
        for line in f:
            if not line.strip() or line.startswith("#"):
                continue
            symbol, debugid = line.strip().split("/")[-3:-1]
            filename = symbol.replace(".pdb", ".sym")
            uri = "/".join([symbol, debugid, filename])
            if search and search.lower() not in uri.lower():
                continue
            uris.add(uri)
    return list(uris)


def send(base_url, number_files=1, search=None):
    uris = _load(search=search)
    for uri in random.sample(uris, min(len(uris), number_files)):
        url = base_url + "/" + uri
        print("URI:", uri)
        response = requests.get(url, allow_redirects=False)
        if response.status_code == 302:
            print("Yay!", response.headers["Location"])
        else:
            print(response.status_code, repr(response.content))
        print()


@click.command()
@click.option("-n", "--number-files", default=1, type=int)
@click.option("-s", "--search", default=None)
@click.argument("url", nargs=1, required=False)
def run(
    url=None,
    search=None,
    number_files=1,
):
    url = url or "http://localhost:8000"
    send(url, number_files=number_files, search=search)


if __name__ == "__main__":
    run()
