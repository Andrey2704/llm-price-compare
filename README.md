# llm-price-compare

![tests](https://github.com/Andrey2704/llm-price-compare/actions/workflows/tests.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

CLI для сравнения цен LLM API между провайдерами: DeepSeek, Groq, Google AI Studio, Moonshot AI (Kimi K3), OpenRouter.

Без зависимостей и без сетевых запросов — считает по снимку цен из `prices.json` (USD за 1M токенов, снимок на **2026-09-24**). Провайдеры меняют цены; перед пополнением сверяйтесь с их страницами, а `validate` подскажет, когда снимок устарел.

## Возможности

- **`list`** — таблица моделей с сортировкой по входу, выходу, стоимости под ваш объём, контексту или имени
- **`top`** — самые дешёвые варианты под конкретный объём токенов
- **`cost`** — построчный расчёт стоимости одной модели с примечанием провайдера
- **`compare`** — несколько моделей бок о бок, включая итоговую стоимость
- **`validate`** — проверка целостности `prices.json` и свежести снимка (CI-friendly, код возврата 1 при ошибках)
- **Экспорт** `--format json|csv` для `list` и `compare` — удобно для скриптов и таблиц
- **Фильтры** `--free`, `--provider`, `--query`

## Установка

Нужен только Python 3.9+.

```bash
# как утилиту в PATH
pipx install git+https://github.com/Andrey2704/llm-price-compare

# или из локальной копии
git clone https://github.com/Andrey2704/llm-price-compare
cd llm-price-compare
pip install -e .
```

Без установки тоже работает — достаточно `python llm_price_compare.py <команда>`.

## Быстрый старт

```bash
llm-price-compare list
```

```
Модель                         Провайдер                     Вход     Выход  Контекст      Итого
------------------------------------------------------------------------------------------------
moonshotai/kimi-k3:free        OpenRouter                    free      free  1M             free
llama-3.3-70b-versatile        Groq                         $0.05     $0.08  128K          $0.09  free-tier
deepseek-v4-flash              DeepSeek (direct)            $0.14     $0.28  128K          $0.28
gemini-flash-lite              Google AI Studio             $0.30     $2.50  1M            $1.55  free-tier
kimi-k3                        Moonshot AI (direct)         $3.00    $15.00  1M           $10.50
moonshotai/kimi-k3             OpenRouter                   $3.30    $16.50  1M           $11.55
```

Колонка «Итого» считается для объёма по умолчанию — 1M входных и 0.5M выходных токенов. Меняется флагами `--in` / `--out`.

```bash
# топ-3 под свой объём
llm-price-compare top -n 3 --in 2000000 --out 1000000

# только бесплатные варианты
llm-price-compare list --free

# точная стоимость одной модели
llm-price-compare cost --model kimi-k3 --in 500000 --out 200000

# сравнение и выгрузка в CSV
llm-price-compare compare deepseek-v4-flash kimi-k3 --format csv > prices.csv

# проверка данных (в CI падает с кодом 1, если что-то не так)
llm-price-compare validate --max-age-days 90
```

## Команды

| Команда | Что делает | Ключевые флаги |
|---|---|---|
| `list` | таблица моделей | `--sort input\|output\|blended\|context\|name`, `--free`, `--provider`, `--query`, `--format` |
| `top` | самые дешёвые под объём | `-n`, `--in`, `--out`, `--free` |
| `cost` | стоимость одной модели | `--model`, `--in`, `--out`, `--format table\|json` |
| `compare` | сравнение 2+ моделей | позиционные id, `--format` |
| `validate` | проверка `prices.json` | `--max-age-days` |

Общий флаг `--data PATH` подставляет другой файл цен — удобно для экспериментов и тестов.

## Формат данных

`prices.json` — снимок цен, а не прайс-лист в реальном времени:

```json
{
  "updated": "2026-09-24",
  "currency": "USD",
  "unit": "per 1M tokens",
  "models": [
    {
      "id": "deepseek-v4-flash",
      "provider": "DeepSeek (direct)",
      "input": 0.14,
      "output": 0.28,
      "context_k": 128,
      "free_tier": false,
      "note": "самый дешёвый рабочий вариант; оплата картой US проверялась 2026-09-24"
    }
  ]
}
```

Обязательные поля: `id`, `provider`, `input`, `output`, `context_k`. `free_tier` и `note` — опциональные.

## Разработка

```bash
python -m unittest discover -s . -p "test_*.py" -v
```

23 теста, без внешних зависимостей. CI гоняет их на Python 3.9, 3.11 и 3.13 и дополнительно вызывает `validate`.

## Дорожная карта

- [ ] автоматическая сверка цен с публичными прайс-страницами провайдеров
- [ ] учёт кэширования промптов (cached input) и батч-скидок
- [ ] сравнение с учётом лимитов RPM/TPM, а не только цены за токен
- [ ] конвертация валют по курсу на дату снимка

## Лицензия

MIT — см. [LICENSE](LICENSE).
