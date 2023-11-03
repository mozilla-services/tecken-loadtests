#1/bin/bash
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Usage: sym_compare.sh STACK
#
# Compares the response from Eliot AWS stage with Eliot GCP stage. Update the
# urls at the top of the script before using.

# Stage
URL1=https://symbolication.stage.mozaws.net/symbolicate/v5
URL2=https://stage.eliot.nonprod.dataservices.mozgcp.net/symbolicate/v5

# Prod
# URL1=https://symbolication.services.mozilla.com/symbolicate/v5
# URL2=https://prod.eliot.prod.dataservices.mozgcp.net/symbolicate/v5

./bin/symbolicate.py compare ${URL1} ${URL2} $1