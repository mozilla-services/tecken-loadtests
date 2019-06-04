#!/bin/bash

set -e

# Runs through downloading, uploading, and symbolication tests.

# Run this in the Docker container.

USAGE="Usage: test_env.sh [dev|stage|prod]"

if [[ $# -eq 0 ]]; then
    echo "${USAGE}"
    exit 1;
fi
case $1 in
    "dev") 
        HOST=https://symbols.dev.mozaws.net/
        ;;
    "stage")
        HOST=https://symbols.stage.mozaws.net/
        ;;
    "prod")
        HOST=https://symbols.mozilla.org/
        ;;
    *)
        echo "${USAGE}"
        exit 1;
        ;;
esac

echo "HOST: ${HOST}"
echo ""

# Test uploading -- requires AUTH_TOKEN in environment
# FIXME: if upload-zips doesn't exist, create it here
# mkdir upload-zips
# python bin/make-symbol-zip.py --save-dir upload-zips
echo ">>> UPLOAD TEST"
python bin/upload-symbol-zips.py --timeout=600 ${HOST}
echo ""

# Test upload by download url
echo ">>> UPLOAD BY DOWNLOAD TEST"
URL=$(python bin/list-firefox-symbols-zips.py --url-only --number=1)
python bin/upload-symbol-zips.py --timeout=600 --download-url=${URL} --number=1 --max-size=1500mb ${HOST}
echo ""

# Test downloading
echo ">>> DOWNLOAD TEST"
python bin/download.py --max-requests=50 ${HOST} downloading/symbol-queries-groups.csv
echo ""

# Test symbolication API
echo ">>> SYMBOLICATION TEST"
python bin/symbolication.py --limit=10 stacks ${HOST}symbolicate/v5
