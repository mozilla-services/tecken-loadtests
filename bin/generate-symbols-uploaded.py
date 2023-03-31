# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Generate symbols-uploaded/YYYY-MM-DD.json.gz files"""

import datetime
import os
import json
import shutil
import gzip

import click
import requests


@click.command()
@click.option(
    "--date",
)
def run(
    date=None,
):
    url = "https://crash-stats.mozilla.com/api/UploadedSymbols/"
    try:
        auth_token = os.environ["AUTH_TOKEN"]
    except KeyError:
        raise click.ClickException(
            "You have to set environment variable AUTH_TOKEN first."
        ) from None

    if not date:
        date = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    response = requests.get(
        url,
        {
            "start_date": date,
            "end_date": date,
        },
        headers={
            "auth-token": auth_token,
        },
    )
    fn = os.path.join("symbols-uploaded", "{}.json".format(date))
    with open(fn, "w") as f:
        json.dump(response.json(), f, indent=2)
    with open(fn, "rb") as f_in:
        with gzip.open(fn + ".gz", "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
            click.echo(
                "Generated {} ({:.1f}KB)".format(
                    fn + ".gz", os.stat(fn + ".gz").st_size / 1024
                )
            )
    os.remove(fn)


if __name__ == "__main__":
    run()
