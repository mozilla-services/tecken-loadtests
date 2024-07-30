#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: ./loadtest_normal.sh ENV [RUNNAME]
#
# Run inside the Docker container.

cd "$(dirname -- "$0")"
. loadtest_functions.sh

export HOST="$(tecken_base_url "$1")"
export TARGET_ENV=$1
USERS="3"
RUNTIME="4m"
RUNNAME_SUFFIX="$1$2-normal"
run_loadtest
