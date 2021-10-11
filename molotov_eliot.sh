#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: ./molotov_eliot.sh [stage|prod]
#
# Run it in the Docker container.

DURATION=600
STAGE_API_URL="https://symbolication.stage.mozaws.net/symbolicate/v5"
PROD_API_URL="https://symbolication.services.mozilla.com/symbolication/v5"

if [[ "$1" == "stage" ]]; then
    export API_URL=${STAGE_API_URL}
elif [[ "$1" == "prod" ]]; then
    export API_URL=${PROD_API_URL}
else
    echo "Unknown environment. Use 'stage' or 'prod'. Exiting."
    exit 1
fi

molotov --workers=5 --processes=5 -d ${DURATION} loadtest-eliot/loadtest.py
