#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Usage: bin/run_lint.sh

set -eo pipefail

PYTHON_VERSION=$(python --version)

echo "black (${PYTHON_VERSION})"
black $1 bin locust-eliot

echo "ruff (${PYTHON_VERSION})"
ruff bin locust-eliot
