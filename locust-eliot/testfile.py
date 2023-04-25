# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import pathlib
import random
import time

import jsonschema
from locust import HttpUser, task
from locust import events


TIMEOUT = 120
SCHEMA = None
PAYLOADS = []
SCHEMADIR = "../schemas/"
STACKSDIR = "../stacks/"


def load_schema(path):
    schema = json.loads(path.read_text())
    jsonschema.Draft7Validator.check_schema(schema)
    return schema


def load_stack(path):
    return json.loads(path.read_text())


@events.init.add_listener
def system_setup(environment, **kwargs):
    """Set up test system."""
    global SCHEMA

    # This is a copy of the one in the tecken repo
    schema_path = pathlib.Path(SCHEMADIR) / "symbolicate_api_response_v5.json"
    SCHEMA = load_schema(schema_path)
    print("Schema loaded.")

    # Stacks are in the parent directory
    stacks_dir = pathlib.Path(STACKSDIR)
    for path in stacks_dir.glob("*.json"):
        path = path.resolve()
        stack = load_stack(path)
        PAYLOADS.append((str(path), stack))

    print(f"Stacks loaded: {len(PAYLOADS)}")


class WebsiteUser(HttpUser):
    # wait_time = between(5, 15)

    @task
    def symbolicate(self):
        headers = {
            "User-Agent": "eliot-loadtest-locust/1.0",
            "Origin": "http://example.com",
        }

        payload_id = int(random.uniform(0, len(PAYLOADS)))
        payload_path, payload = PAYLOADS[payload_id]

        t = time.time()
        resp = self.client.post(
            "/symbolicate/v5", headers=headers, json=payload, timeout=TIMEOUT
        )

        end_t = time.time()
        delta_t = int(end_t - t)
        assert (
            resp.status_code == 200
        ), f"failed with {resp.status_code}: {payload_path} ({delta_t:,}s)"

        json_data = resp.json()

        try:
            jsonschema.validate(json_data, SCHEMA)
        except jsonschema.exceptions.ValidationError as exc:
            raise AssertionError("response didn't validate") from exc
