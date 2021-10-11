# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import os
import pathlib
import random

import jsonschema
from molotov import global_setup, setup, scenario, get_var, set_var


DEFAULT_API_URL = "https://symbolication.stage.mozaws.net/symbolicate/v5"
SCHEMA = None
PAYLOADS = []


def load_schema(path):
    schema = json.loads(path.read_text())
    jsonschema.Draft7Validator.check_schema(schema)
    return schema


def load_stack(path):
    return json.loads(path.read_text())


@global_setup()
def system_setup(args):
    """Set up test system.

    This is called before anything runs.

    """
    global SCHEMA
    # This is a copy of the one in the tecken repo
    schema_path = pathlib.Path("schemas/symbolicate_api_response_v5.json")
    SCHEMA = load_schema(schema_path)
    print("Schema loaded.")

    # Stacks are in the parent directory
    stacks_dir = pathlib.Path("stacks/")
    for path in stacks_dir.glob("*.json"):
        path = path.resolve()
        stack = load_stack(path)
        PAYLOADS.append((str(path), stack))

    # Set the API url
    api_url = os.environ.get("API_URL", DEFAULT_API_URL)
    set_var("api_url", api_url)

    print(f"Stacks loaded: {len(PAYLOADS)}")
    print(f"Running tests against: {api_url}")


@setup()
async def worker_setup(worker_id, args):
    """Set the headers.

    NOTE(willkg): The return value is a dict that's passed as keyword arguments
    to aiohttp.ClientSession.

    """
    return {
        "headers": {
            "User-Agent": "tecken-systemtests",
            "Origin": "http://example.com",
        }
    }


@scenario(weight=100)
async def scenario_request_stack(session):
    api_url = get_var("api_url")

    payload_id = int(random.uniform(0, len(PAYLOADS)))
    payload_path, payload = PAYLOADS[payload_id]
    async with session.post(api_url, json=payload) as resp:
        assert resp.status == 200, f"failed with {resp.status}: {payload_path}"

        json_data = await resp.json()

        try:
            jsonschema.validate(json_data, SCHEMA)
        except jsonschema.exceptions.ValidationError:
            raise AssertionError("response didn't validate")
