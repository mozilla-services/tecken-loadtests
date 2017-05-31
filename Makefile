.PHONY: symbolicate-locally download-locally symbolicate-dev

help:
	@echo "Welcome to the tecken-loadtest\n"
	@echo "The list of commands:\n"
	@echo "  symbolicate-locally    Do a lot of symbolications locally"
	@echo "  symbolicate-dev        Do a lot of symbolications on Dev server"
	@echo "  download-locally       Do a lot of symbol downloads locally"


symbolicate-locally:
	python symbolication.py stacks http://localhost:8000

symbolicate-dev:
	python symbolication.py stacks https://symbols.dev.mozaws.net

download-locally:
	python download.py http://localhost:8000 downloading/symbol-queries-groups.csv downloading/socorro-missing.csv
