#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Usage: bin/run_lint.sh [--fix]
#
# Runs linting and code fixing.
#
# This should be called from inside a container.

set -e

FILES="bin locust*"
PYTHON_VERSION=$(python --version)

cd /app

if [[ $1 == "--format" ]]; then
    echo ">>> ruff fix (${PYTHON_VERSION})"
    ruff format $FILES
    ruff check --fix $FILES
else
    echo ">>> ruff (${PYTHON_VERSION})"
    ruff check $FILES
    ruff format --check $FILES
fi
