"""llm-price-compare — сравнение цен LLM API между провайдерами.

Данные лежат в ``prices.json``: снимок цен в USD за 1M токенов.
Модуль не делает сетевых запросов — только считает по снимку.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

DATA_FILE = Path(__file__).parent / "prices.json"

SORT_KEYS = ("input", "output", "blended", "context", "name")
EXPORT_FORMATS = ("table", "json", "csv")

REQUIRED_FIELDS = ("id", "provider", "input", "output", "context_k")


# --- загрузка и валидация -------------------------------------------------


def load_data(path=DATA_FILE) -> dict:
    """Читает prices.json и проверяет минимальную структуру."""
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("models"), list):
        raise ValueError(f"{path}: ожидался объект с массивом 'models'")
    return data


def validate_data(data: dict) -> List[str]:
    """Возвращает список проблем в данных. Пустой список — всё в порядке."""
    problems: List[str] = []
    seen = set()
    for index, model in enumerate(data.get("models", []), start=1):
        where = f"models[{index}]"
        for field in REQUIRED_FIELDS:
            if field not in model:
                problems.append(f"{where}: нет обязательного поля '{field}'")
        model_id = model.get("id")
        if model_id in seen:
            problems.append(f"{where}: повторяющийся id '{model_id}'")
        seen.add(model_id)
        for field in ("input", "output"):
            value = model.get(field)
            if not isinstance(value, (int, float)):
                problems.append(f"{where}: '{field}' должен быть числом")
            elif value < 0:
                problems.append(f"{where}: отрицательная цена в '{field}'")
        context = model.get("context_k")
        if isinstance(context, (int, float)) and context <= 0:
            problems.append(f"{where}: 'context_k' должен быть больше нуля")
    return problems


def data_age_days(data: dict, today=None) -> Optional[int]:
    """Сколько дней снимку цен. None, если дата отсутствует или битая."""
    raw = data.get("updated")
    if not raw:
        return None
    try:
        updated = datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return ((today or date.today()) - updated).days


# --- расчёты --------------------------------------------------------------


def blended_cost(model: dict, in_tokens: int, out_tokens: int) -> float:
    """Стоимость запроса в USD по ценам за 1M токенов."""
    return (
        model["input"] * in_tokens / 1_000_000
        + model["output"] * out_tokens / 1_000_000
    )


def fmt_price(value: float) -> str:
    if value == 0:
        return "free"
    return f"${value:.2f}" if value >= 0.01 else f"${value:.4f}"


def fmt_tokens(count: int) -> str:
    """1000000 -> '1 000 000'."""
    return f"{count:,}".replace(",", " ")


def fmt_context(context_k: int) -> str:
    return f"{context_k // 1000}M" if context_k >= 1000 else f"{context_k}K"


# --- выборка --------------------------------------------------------------


def filter_models(
    models: Iterable[dict],
    free_only: bool = False,
    provider: Optional[str] = None,
    query: Optional[str] = None,
) -> List[dict]:
    """Фильтр по free-тиру, провайдеру и подстроке в id/имени провайдера."""
    selected = list(models)
    if free_only:
        selected = [m for m in selected if m.get("free_tier")]
    if provider:
        needle = provider.lower()
        selected = [m for m in selected if needle in str(m["provider"]).lower()]
    if query:
        needle = query.lower()
        selected = [
            m
            for m in selected
            if needle in str(m["id"]).lower() or needle in str(m["provider"]).lower()
        ]
    return selected


def sort_models(
    models: Sequence[dict],
    key: str = "input",
    in_tokens: int = 0,
    out_tokens: int = 0,
) -> List[dict]:
    if key == "name":
        return sorted(models, key=lambda m: m["id"])
    if key == "context":
        return sorted(models, key=lambda m: m["context_k"], reverse=True)
    if key == "blended":
        return sorted(models, key=lambda m: blended_cost(m, in_tokens, out_tokens))
    if key in ("input", "output"):
        return sorted(models, key=lambda m: m[key])
    raise ValueError(f"неизвестный ключ сортировки: {key}")


# --- вывод ----------------------------------------------------------------


def to_records(
    models: Iterable[dict], in_tokens: int, out_tokens: int
) -> List[Dict[str, object]]:
    """Плоские записи для экспорта — без вложенности."""
    records = []
    for m in models:
        records.append(
            {
                "id": m["id"],
                "provider": m["provider"],
                "input_usd_per_1m": m["input"],
                "output_usd_per_1m": m["output"],
                "context_k": m["context_k"],
                "free_tier": bool(m.get("free_tier")),
                "blended_usd": round(blended_cost(m, in_tokens, out_tokens), 6),
                "note": m.get("note", ""),
            }
        )
    return records


def render_table(
    models: Sequence[dict],
    in_tokens: Optional[int] = None,
    out_tokens: Optional[int] = None,
) -> str:
    show_blended = in_tokens is not None and out_tokens is not None
    head = f"{'Модель':<30} {'Провайдер':<24} {'Вход':>9} {'Выход':>9}  {'Контекст':<8}"
    if show_blended:
        head += f" {'Итого':>10}"
    lines = [head, "-" * len(head)]
    for m in models:
        row = (
            f"{str(m['id'])[:30]:<30} {str(m['provider'])[:24]:<24} "
            f"{fmt_price(m['input']):>9} {fmt_price(m['output']):>9}  "
            f"{fmt_context(m['context_k']):<8}"
        )
        if show_blended:
            row += f" {fmt_price(blended_cost(m, in_tokens, out_tokens)):>10}"
        if m.get("free_tier") and m["input"] > 0:
            row += "  free-tier"
        lines.append(row)
    return "\n".join(lines)


def render_json(records: Sequence[dict], meta: dict) -> str:
    payload = {"meta": meta, "models": list(records)}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_csv(records: Sequence[dict]) -> str:
    if not records:
        return ""
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=list(records[0].keys()), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(records)
    return buffer.getvalue().rstrip("\n")


def emit(models: Sequence[dict], meta: dict, fmt: str) -> None:
    records = to_records(models, meta["in_tokens"], meta["out_tokens"])
    if fmt == "json":
        print(render_json(records, meta))
    elif fmt == "csv":
        print(render_csv(records))
    else:
        print(render_table(models, meta["in_tokens"], meta["out_tokens"]))


# --- команды --------------------------------------------------------------


def cmd_list(data: dict, args) -> int:
    models = filter_models(
        data["models"], free_only=args.free, provider=args.provider, query=args.query
    )
    models = sort_models(models, args.sort, args.in_tokens, args.out_tokens)
    if not models:
        print("Ничего не найдено по заданным фильтрам.", file=sys.stderr)
        return 1
    meta = {
        "updated": data.get("updated"),
        "currency": data.get("currency", "USD"),
        "unit": data.get("unit", "per 1M tokens"),
        "in_tokens": args.in_tokens,
        "out_tokens": args.out_tokens,
        "sort": args.sort,
        "count": len(models),
    }
    emit(models, meta, args.format)
    return 0


def cmd_top(data: dict, args) -> int:
    models = filter_models(data["models"], free_only=args.free)
    ranked = sort_models(models, "blended", args.in_tokens, args.out_tokens)[: args.n]
    if not ranked:
        print("Нет моделей для расчёта.", file=sys.stderr)
        return 1
    print(
        f"Топ-{len(ranked)} по стоимости для {fmt_tokens(args.in_tokens)} вход / "
        f"{fmt_tokens(args.out_tokens)} выход:"
    )
    for i, m in enumerate(ranked, 1):
        cost = blended_cost(m, args.in_tokens, args.out_tokens)
        suffix = "  [free]" if m.get("free_tier") else ""
        print(f"  {i}. {m['id']} ({m['provider']}) — {fmt_price(cost)}{suffix}")
    return 0


def cmd_cost(data: dict, args) -> int:
    found = [m for m in data["models"] if m["id"] == args.model]
    if not found:
        print(f"Модель '{args.model}' не найдена. Список: `list`.", file=sys.stderr)
        return 1
    m = found[0]
    total = blended_cost(m, args.in_tokens, args.out_tokens)
    if args.format == "json":
        print(
            render_json(
                to_records([m], args.in_tokens, args.out_tokens),
                {"in_tokens": args.in_tokens, "out_tokens": args.out_tokens},
            )
        )
        return 0
    print(f"{m['id']} ({m['provider']})")
    print(
        f"  вход  {fmt_tokens(args.in_tokens):>12} tok x {fmt_price(m['input'])}/1M"
        f" = {fmt_price(m['input'] * args.in_tokens / 1_000_000)}"
    )
    print(
        f"  выход {fmt_tokens(args.out_tokens):>12} tok x {fmt_price(m['output'])}/1M"
        f" = {fmt_price(m['output'] * args.out_tokens / 1_000_000)}"
    )
    print(f"  ИТОГО: {fmt_price(total)}")
    if m.get("note"):
        print(f"  Примечание: {m['note']}")
    return 0


def cmd_compare(data: dict, args) -> int:
    models = [m for m in data["models"] if m["id"] in args.models]
    missing = set(args.models) - {m["id"] for m in models}
    if missing:
        print(f"Не найдены: {', '.join(sorted(missing))}", file=sys.stderr)
    if len(models) < 2:
        print("Нужно минимум 2 существующие модели для сравнения.", file=sys.stderr)
        return 1
    if args.format in ("json", "csv"):
        emit(
            models,
            {"in_tokens": args.in_tokens, "out_tokens": args.out_tokens},
            args.format,
        )
        return 0

    width = 24
    print(f"{'':<14}" + "".join(f"{str(m['id'])[:22]:>{width}}" for m in models))
    rows = [
        ("Вход /1M", [fmt_price(m["input"]) for m in models]),
        ("Выход /1M", [fmt_price(m["output"]) for m in models]),
        ("Контекст", [fmt_context(m["context_k"]) for m in models]),
        (
            "Стоимость",
            [
                fmt_price(blended_cost(m, args.in_tokens, args.out_tokens))
                for m in models
            ],
        ),
    ]
    for label, cells in rows:
        print(f"{label:<14}" + "".join(f"{c:>{width}}" for c in cells))
    return 0


def cmd_validate(data: dict, args) -> int:
    problems = validate_data(data)
    age = data_age_days(data)
    if problems:
        print(f"Найдено проблем: {len(problems)}", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"Данные корректны: моделей — {len(data['models'])}.")
    if age is not None:
        print(f"Снимок от {data.get('updated')} ({age} дн. назад).")
        if age > args.max_age_days:
            print(
                f"Внимание: снимку больше {args.max_age_days} дней — цены могли измениться.",
                file=sys.stderr,
            )
    return 0


# --- CLI ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-price-compare",
        description="Сравнение цен LLM API (данные: prices.json)",
    )
    parser.add_argument("--data", default=str(DATA_FILE), help="путь к prices.json")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_volume(sp):
        sp.add_argument("--in", dest="in_tokens", type=int, default=1_000_000)
        sp.add_argument("--out", dest="out_tokens", type=int, default=500_000)

    sp = sub.add_parser("list", help="список моделей с фильтрами и сортировкой")
    add_volume(sp)
    sp.add_argument("--sort", choices=SORT_KEYS, default="input")
    sp.add_argument("--free", action="store_true", help="только модели с free-тиром")
    sp.add_argument("--provider", help="подстрока в названии провайдера")
    sp.add_argument("--query", help="подстрока в id модели или провайдере")
    sp.add_argument("--format", choices=EXPORT_FORMATS, default="table")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("top", help="самые дешёвые под ваш объём")
    add_volume(sp)
    sp.add_argument("-n", type=int, default=3)
    sp.add_argument("--free", action="store_true")
    sp.set_defaults(func=cmd_top)

    sp = sub.add_parser("cost", help="стоимость одной модели")
    sp.add_argument("--model", required=True)
    add_volume(sp)
    sp.add_argument("--format", choices=("table", "json"), default="table")
    sp.set_defaults(func=cmd_cost)

    sp = sub.add_parser("compare", help="сравнить 2+ модели бок о бок")
    sp.add_argument("models", nargs="+")
    add_volume(sp)
    sp.add_argument("--format", choices=EXPORT_FORMATS, default="table")
    sp.set_defaults(func=cmd_compare)

    sp = sub.add_parser("validate", help="проверить prices.json")
    sp.add_argument("--max-age-days", type=int, default=90)
    sp.set_defaults(func=cmd_validate)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        data = load_data(args.data)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Не удалось прочитать данные: {exc}", file=sys.stderr)
        return 2
    return args.func(data, args) or 0


if __name__ == "__main__":
    sys.exit(main())
