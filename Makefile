# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Include my.env and export it so variables set in there are available
# in the Makefile.
include my.env
export

# Set these in the environment to override them. This is helpful for
# development if you have file ownership problems because the user
# in the container doesn't match the user on your host.
MYUID ?= 10001
MYGID ?= 10001

DC := $(shell which docker-compose)
STACKSDIR = stacks/

.DEFAULT_GOAL := help
.PHONY: help
help:
	@echo "Usage: make RULE"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' Makefile \
		| grep -v grep \
	    | sed -n 's/^\(.*\): \(.*\)##\(.*\)/\1\3/p' \
	    | column -t  -s '|'
	@echo ""
	@echo "Read README.rst for more details."

my.env:
	@if [ ! -f my.env ]; \
	then \
	echo "Copying my.env.dist to my.env..."; \
	cp my.env.dist my.env; \
	fi

.docker-build:
	make build

.PHONY: build
build:  ## | Build Docker image for testing with
	${DC} build --no-cache --build-arg userid=${MYUID} --build-arg groupid=${MYGID} base
	touch .docker-build

.PHONY: clean
clean:  ## | Delete artifacts
	${DC} stop
	${DC} rm -f
	rm -rf .docker-build

.PHONY: shell
shell: .docker-build  ## | Create a shell in the Docker image
	${DC} run base /bin/bash

.PHONY: buildstacks
buildstacks: .docker-build  ## | Build stacks for testing symbolication
	-mkdir $(STACKSDIR)
	${DC} run base /bin/bash -c "bin/fetch-crashids.py --num-results=1000 | bin/make-stacks.py save $(STACKSDIR)"
	@echo "`ls $(STACKSDIR)/*.json | wc -l` stacks total."

.PHONY: symbolicate-locally
symbolicate-locally:  ## | Run symbolication against localhost
	python symbolication.py stacks http://localhost:8050

.PHONY: symbolicate-stage
symbolicate-stage:  ## | Run symbolication against stage
	python symbolication.py stacks https://symbols.stage.mozaws.net

.PHONY: download-locally
download-locally:  ## | Run download test against localhost
	python download.py http://localhost:8000 downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

.PHONY: download-stage
download-stage:  ## | Run download test against stage
	python download.py https://symbols.stage.mozaws.net downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

.PHONY: download-prod
download-prod:  ## | Run download test against prod
	python download.py https://symbols.mozilla.org downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

.PHONY: make-symbol-zip
make-symbol-zip:  ## | Make a symbols.zip file for uploading tests
	python make-symbol-zip.py
