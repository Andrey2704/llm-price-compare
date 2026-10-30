.PHONY: test validate lint run
PY ?= python

test:            ## прогнать тесты
	$(PY) -m unittest discover -s . -p "test_*.py" -v

validate:        ## проверить целостность и свежесть prices.json
	$(PY) llm_price_compare.py validate --max-age-days 90

lint:            ## линт, если установлен ruff
	-ruff check .

run:             ## таблица моделей
	$(PY) llm_price_compare.py list
