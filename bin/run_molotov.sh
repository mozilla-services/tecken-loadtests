#!/bin/bash

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Run this in the container.

URL_SERVER=${URL_SERVER} molotov -c -v -d ${TEST_DURATION} loadtest.py
