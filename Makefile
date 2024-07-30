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

DOCKER := $(shell which docker)
DC=${DOCKER} compose
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

.PHONY: lint
lint:  ## | Lint code in this repo
	${DC} run base /bin/bash -c "bin/run_lint.sh"

.PHONY: format
format:  ## | Format code in this repo
	${DC} run base /bin/bash -c "bin/run_lint.sh --format"

.PHONY: clean
clean:  ## | Delete artifacts
	${DC} stop
	${DC} rm -f
	rm -rf .docker-build

.PHONY: shell
shell: .docker-build  ## | Create a shell in the Docker image
	${DC} run base /bin/bash
