#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: ./locust_eliot.sh ENV [RUNNAME]
#
# Run it in the Docker container.

AWS_STAGE_HOST="https://symbolication.stage.mozaws.net"
AWS_PROD_HOST="https://symbolication.services.mozilla.com"

GCP_STAGE_HOST="https://stage.eliot.nonprod.dataservices.mozgcp.net"
GCP_PROD_HOST="https://prod.eliot.prod.dataservices.mozgcp.net"


if [[ "$1" == "aws-stage" ]]; then
    export HOST=${AWS_STAGE_HOST}

elif [[ "$1" == "aws-prod" ]]; then
    export HOST=${AWS_PROD_HOST}

elif [[ "$1" == "gcp-stage" ]]; then
    export HOST=${GCP_STAGE_HOST}

elif [[ "$1" == "gcp-prod" ]]; then
    export HOST=${GCP_PROD_HOST}

else
    echo "Unknown environment. Use 'aws-stage', 'aws-prod', 'gcp-stage', or 'gcp-prod'."
    echo "Exiting."
    exit 1
fi

# Runname includes environment and any second argument
RUNNAME="$(date +'%Y%m%d-%H0000')-$1$2"

RUNTIME="5m"
USERS="10"

LOCUST_FLAGS="--print-stats --headless"

echo ">>> Host:    ${HOST}"
echo ">>> Runname: ${RUNNAME}"
echo ">>> Locust start...."
locust -f locust-eliot/testfile.py \
    --host="${HOST}" \
    --users="${USERS}" \
    --run-time="${RUNTIME}" \
    --csv="${RUNNAME}" \
    ${LOCUST_FLAGS}
echo ">>> Locust end."
