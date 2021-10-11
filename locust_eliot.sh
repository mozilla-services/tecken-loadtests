#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: ./molotov_eliot.sh [stage|prod]
#
# Run it in the Docker container.

DURATION=600

STAGE_HOST="https://symbolication.stage.mozaws.net"
PROD_HOST="https://symbolication.services.mozilla.com"

if [[ "$1" == "stage" ]]; then
    export HOST=${STAGE_HOST}
elif [[ "$1" == "prod" ]]; then
    export HOST=${PROD_HOST}
else
    echo "Unknown environment. Use 'stage' or 'prod'. Exiting."
    exit 1
fi

locust -f locust-eliot/testfile.py --host "${HOST}" --users 60 --run-time "10m" --print-stats --headless
