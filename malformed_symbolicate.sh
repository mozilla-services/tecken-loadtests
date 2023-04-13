#!/bin/bash
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Usage: malformed_symbolicate.sh
#
# Before using, change the variables at the top to the ones you want.

# HOST=https://symbolication.stage.mozaws.net
# HOST=https://stage.eliot.nonprod.dataservices.mozgcp.net
HOST=https://prod.eliot.prod.dataservices.mozgcp.net

# APIVERSION=v4
APIVERSION=v5

echo ">>> Valid request."
curl -v \
    --compressed \
    -H "Content-Type: application/json" \
    -H "Accept-Encoding: gzip" \
    -d '{"stacks":[[[0,452494],[0,452100]]],"memoryMap":[["mozglue.pdb","EE0CFCB520F944314C4C44205044422E1"]]}' \
    ${HOST}/symbolicate/${APIVERSION}
echo ""
echo "Expected: This should spit out a valid response."
read -p "next? " readvar

echo ">>> Wrong content-type."
curl -v \
    --compressed \
    -H "Content-Type: text/html" \
    -H "Accept-Encoding: gzip" \
    -d '{"stacks":[[[0,452494],[0,452100]]],"memoryMap":[["mozglue.pdb","EE0CFCB520F944314C4C44205044422E1"]]}' \
    ${HOST}/symbolicate/${APIVERSION}
echo ""
echo "Expected: This should also spit out a valid response. For some reason, Eliot ignores the content type."
read -p "next? " readvar

echo ">>> No payload."
curl -v \
    -X POST \
    --compressed \
    -H "Content-Type: application/json" \
    -H "Accept-Encoding: gzip" \
    ${HOST}/symbolicate/${APIVERSION}
echo ""
echo "Expected: This should also spit out something like 'Payload is not valid JSON'."
read -p "next? " readvar

echo ">>> Missing stacks data."
curl -v \
    --compressed \
    -H "Content-Type: application/json" \
    -H "Accept-Encoding: gzip" \
    -d '{"memoryMap":[["mozglue.pdb","EE0CFCB520F944314C4C44205044422E1"]]}' \
    ${HOST}/symbolicate/${APIVERSION}
echo ""
echo "Expected: This should spit out something like 'job 0 is invalid: no stacks specified'."
read -p "next? " readvar

echo ">>> Stacks data is malformed."
curl -v \
    --compressed \
    -H "Content-Type: application/json" \
    -H "Accept-Encoding: gzip" \
    -d '{"stacks":[[[0,452494,5],[0]]],"memoryMap":[["mozglue.pdb","EE0CFCB520F944314C4C44205044422E1"]]}' \
    ${HOST}/symbolicate/v4
echo ""
echo "Expected: This should spit out something like 'job 0 has invalid stacks: stack 0 frame 0 is not a list of two items'."
echo ""
echo "Done"
