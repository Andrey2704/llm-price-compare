"""llm-price-compare: сравнение цен LLM API между провайдерами."""

import argparse
import json
import sys
from pathlib import Path

DATA_FILE = Path(__file__).parent / "prices.json"


def load_models(path=DATA_FILE):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data


def blended_cost(model, in_tokens, out_tokens):
    return (
        model["input"] * in_tokens / 1_000_000
        + model["output"] * out_tokens / 1_000_000
    )


def fmt_price(v):
    return f"${v:.2f}" if v >= 0.01 else f"${v:.4f}"


def cmd_list(data, args):
    models = sorted(data["models"], key=lambda m: m["input"])
    print(f"{'Модель':<32} {'Провайдер':<26} {'Вход':>8} {'Выход':>8}  Контекст")
    print("-" * 92)
    for m in models:
        ctx = f"{m['context_k']}K" if m["context_k"] < 1000 else f"{m['context_k'] // 1000}M"
        free = " [free]" if m["free_tier"] else ""
        print(f"{m['id']:<32} {m['provider']:<26} {fmt_price(m['input']):>8} "
              f"{fmt_price(m['output']):>8}  {ctx}{free}")


def cmd_top(data, args):
    models = sorted(
        data["models"],
        key=lambda m: blended_cost(m, args.in_tokens, args.out_tokens),
    )[: args.n]
    for i, m in enumerate(models, 1):
        cost = blended_cost(m, args.in_tokens, args.out_tokens)
        print(f"{i}. {m['id']} ({m['provider']}) — {fmt_price(cost)} "
              f"за {args.in_tokens:,} вход / {args.out_tokens:,} выход")


def cmd_cost(data, args):
    found = [m for m in data["models"] if m["id"] == args.model]
    if not found:
        print(f"Модель '{args.model}' не найдена. См. `list`.", file=sys.stderr)
        return 1
    m = found[0]
    cost = blended_cost(m, args.in_tokens, args.out_tokens)
    print(f"{m['id']} ({m['provider']})")
    print(f"  вход  {args.in_tokens:>12,} tok x {fmt_price(m['input'])}/1M"
          f" = {fmt_price(m['input'] * args.in_tokens / 1_000_000)}")
    print(f"  выход {args.out_tokens:>12,} tok x {fmt_price(m['output'])}/1M"
          f" = {fmt_price(m['output'] * args.out_tokens / 1_000_000)}")
    print(f"  ИТОГО: {fmt_price(cost)}")
    if m["note"]:
        print(f"  Примечание: {m['note']}")
    return 0


def cmd_compare(data, args):
    models = [m for m in data["models"] if m["id"] in args.models]
    missing = set(args.models) - {m["id"] for m in models}
    if missing:
        print(f"Не найдены: {', '.join(missing)}", file=sys.stderr)
    if len(models) < 2:
        print("Нужно минимум 2 существующие модели для сравнения.", file=sys.stderr)
        return 1
    print(f"{'':<14}" + "".join(f"{m['id'][:20]:>22}" for m in models))
    for label, key in [("Вход /1M", "input"), ("Выход /1M", "output")]:
        print(f"{label:<14}" + "".join(f"{fmt_price(m[key]):>22}" for m in models))
    print(f"{'Контекст':<14}" + "".join(f"{m['context_k']}K{'':>18}" for m in models))
    return 0


def main():
    p = argparse.ArgumentParser(
        description="Сравнение цен LLM API (данные: prices.json)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="список всех моделей по цене входа")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("top", help=f"самые дешёвые для вашего объёма")
    sp.add_argument("-n", type=int, default=3)
    sp.add_argument("--in", dest="in_tokens", type=int, default=1_000_000)
    sp.add_argument("--out", dest="out_tokens", type=int, default=500_000)
    sp.set_defaults(func=cmd_top)

    sp = sub.add_parser("cost", help="стоимость конкретной модели")
    sp.add_argument("--model", required=True)
    sp.add_argument("--in", dest="in_tokens", type=int, default=1_000_000)
    sp.add_argument("--out", dest="out_tokens", type=int, default=500_000)
    sp.set_defaults(func=cmd_cost)

    sp = sub.add_parser("compare", help="сравнить 2+ модели")
    sp.add_argument("models", nargs="+")
    sp.set_defaults(func=cmd_compare)

    args = p.parse_args()
    data = load_models()
    sys.exit(args.func(data, args) or 0)


if __name__ == "__main__":
    main()
