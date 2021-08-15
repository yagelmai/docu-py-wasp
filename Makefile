PERFHOME = /p/dpg/arch/perfhome
PYTHON   = $(PERFHOME)/python/miniconda

all: lint test

lint:
	@echo "[ Flake8 ]"
	@$(PYTHON)/bin/flake8 --ignore=D100,D101,D102,D103,D104,D105,D106,D107,D204,D205,D400,D401,D413,E241,W504,W605 \
		--max-line-length=120 --exclude=dev ./

docu:
	@echo "[ Flake8 ]"
	@$(PYTHON)/bin/flake8 --ignore=D100,D101,D102,D103,D104,D105,D106,D107,D204,D205,D400,D401,D413,E241,W504,W605 \
		--max-line-length=120 --exclude=dev ./

test:
	@echo "[ PyTest ]"
	@$(PYTHON)/bin/pytest -q --disable-pytest-warnings --tb=short --durations=5 \
			--ignore=dev --cov=qtgui --cov=py_wasp.py --cov-report term $(TEST)

clean:
	git clean -xfd

.PHONY: all clean lint test install
