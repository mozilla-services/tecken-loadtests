#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: ./prime_env.sh ENV [RUNNAME]

cd "$(dirname -- "$0")"
. loadtest_functions.sh

HOST="$(eliot_base_url "$1")"
USERS="2"
RUNTIME="10m"
RUNNAME_SUFFIX="$1$2-prime"
run_loadtest
