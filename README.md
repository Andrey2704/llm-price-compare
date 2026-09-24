# llm-price-compare

Утилита для сравнения цен LLM API между провайдерами: DeepSeek, Groq, Google AI Studio, Moonshot AI (Kimi K3), OpenRouter.

Цены в `prices.json` — снимок на **2026-09-24**, в USD за 1M токенов. Провайдеры меняют цены — проверяйте перед пополнением.

## Запуск

Нужен только Python 3.9+ (без внешних зависимостей).

```bash
# список всех моделей, от дешёвых к дорогим
python llm_price_compare.py list

# топ-3 для вашего объёма (по умолчанию 1M вход / 0.5M выход)
python llm_price_compare.py top -n 3 --in 2000000 --out 1000000

# точная стоимость одной модели
python llm_price_compare.py cost --model kimi-k3 --in 500000 --out 200000

# сравнение моделей бок о бок
python llm_price_compare.py compare deepseek-v4-flash kimi-k3 "moonshotai/kimi-k3:free"
```

## Тесты

```bash
python -m unittest test_llm_price_compare.py -v
```

## Как добавить модель

Допишите объект в массив `models` в `prices.json`:

```json
{
  "id": "provider/model-id",
  "provider": "Имя провайдера",
  "input": 1.0,
  "output": 2.0,
  "context_k": 128,
  "free_tier": false,
  "note": "любое примечание"
}
```

## Лицензия

MIT
