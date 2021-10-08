#!/bin/bash

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
