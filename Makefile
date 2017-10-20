.PHONY: symbolicate-locally symbolicate-dev symbolicate-stage download-locally download-dev download-stage make-symbol-zip

help:
	@echo "Welcome to the tecken-loadtest\n"
	@echo "The list of commands:\n"
	@echo "  symbolicate-locally    Do a lot of symbolications locally"
	@echo "  symbolicate-dev        Do a lot of symbolications on Dev server"
	@echo "  symbolicate-stage      Do a lot of symbolications on Stage server"
	@echo "  download-locally       Do a lot of symbol downloads locally"
	@echo "  download-dev           Do a lot of symbol downloads on Dev server"
	@echo "  download-stage         Do a lot of symbol downloads on Stage server"
	@echo "  make-symbol-zip        Generate .zip files to test upload\n"


symbolicate-locally:
	python symbolication.py stacks http://localhost:8000

symbolicate-dev:
	python symbolication.py stacks https://symbols.dev.mozaws.net

symbolicate-stage:
	python symbolication.py stacks https://symbols.stage.mozaws.net

download-locally:
	python download.py http://localhost:8000 downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

download-dev:
	python download.py https://symbols.dev.mozaws.net downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

download-stage:
	python download.py https://symbols.stage.mozaws.net downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

download-prod:
	python download.py https://symbols.mozilla.org downloading/symbol-queries-groups.csv downloading/socorro-missing.csv

make-symbol-zip:
	python make-symbol-zip.py
