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

.PHONY: help
help: default

.PHONY: help
default:
	@echo "Welcome to the tecken-loadtest\n"
	@echo "The list of commands:\n"
	@echo "  symbolicate-locally    Do a lot of symbolications locally"
	@echo "  symbolicate-dev        Do a lot of symbolications on Dev server"
	@echo "  symbolicate-stage      Do a lot of symbolications on Stage server"
	@echo "  download-locally       Do a lot of symbol downloads locally"
	@echo "  download-dev           Do a lot of symbol downloads on Dev server"
	@echo "  download-stage         Do a lot of symbol downloads on Stage server"
	@echo "  make-symbol-zip        Generate .zip files to test upload\n"

my.env:
	@if [ ! -f my.env ]; \
	then \
	echo "Copying my.env.dist to my.env..."; \
	cp my.env.dist my.env; \
	fi

.docker-build:
	make build

.PHONY: build
build:
	${DC} build --no-cache --build-arg userid=${MYUID} --build-arg groupid=${MYGID} base
	touch .docker-build

.PHONY: clean
clean:
	${DC} stop
	${DC} rm -f
	rm -rf .docker-build

.PHONY: shell
shell:
	${DC} run base /bin/bash

.PHONY: symbolicate-locally
symbolicate-locally:
	python symbolication.py stacks http://localhost:8000

.PHONY: symbolicate-dev
symbolicate-dev:
	python symbolication.py stacks https://symbols.dev.mozaws.net

.PHONY: symbolicate-stage
symbolicate-stage:
	python symbolication.py stacks https://symbols.stage.mozaws.net

.PHONY: download-locally
download-locally:
	python download.py http://localhost:8000 downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

.PHONY: download-dev
download-dev:
	python download.py https://symbols.dev.mozaws.net downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

.PHONY: download-stage
download-stage:
	python download.py https://symbols.stage.mozaws.net downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

.PHONY: download-prod
download-prod:
	python download.py https://symbols.mozilla.org downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

.PHONY: make-symbol-zip
make-symbol-zip:
	python make-symbol-zip.py
