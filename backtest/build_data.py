#!/usr/bin/env python3
"""Rebuild backtest/data/backtest.json from the exported CSV tabs.

Swap a future rules version by replacing the CSVs in backtest/data/, then:

    python3 backtest/build_data.py
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


def scrub_crossback(s: str) -> str:
    """Rewrite every visible 'crossback' label for the public site."""
    t = s
    t = re.sub(r"6\s*EMA\s+crossback", "a 15-minute candle closes back above its 6 EMA", t, flags=re.I)
    t = re.sub(r"EMA\s+Crossback", "EMA Bounce", t, flags=re.I)
    t = re.sub(r"Crossback\s+trading\s+rules", "TiltKiller trading rules", t, flags=re.I)
    t = re.sub(r"crossback\s+rules", "trading rules", t, flags=re.I)
    t = re.sub(r"Results:\s*crossback", "Results: trading", t, flags=re.I)
    t = re.sub(r"s_ema-crossback", "s_ema-bounce", t, flags=re.I)
    t = re.sub(r"cross[\s_-]*back", "bounce", t, flags=re.I)
    return t


def scrub_tree(obj):
    if isinstance(obj, dict):
        return {k: scrub_tree(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_tree(v) for v in obj]
    if isinstance(obj, str):
        return scrub_crossback(obj)
    return obj


def read_table(name: str) -> list[dict]:
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build() -> dict:
    lines = (DATA / "results.csv").read_text(encoding="utf-8").splitlines()
    out: dict = {
        "meta": {
            "title": "TiltKiller trading rules v1.6",
            "sheet": lines[0],
            "period": "November 2023 to November 2026 (three years)",
            "r_definition": "1R is the amount you risk on a trade (what you lose if the stop hits).",
            "version": "1.6",
            "as_of": "2026-11-16",
        }
    }

    inp: dict = {}
    for line in lines[lines.index("Input") + 1 :]:
        if line == "Results":
            break
        parts = next(csv.reader([line]))
        if not any(p.strip() for p in parts):
            continue
        for idx, p in enumerate(parts):
            if p == "Slippage per side":
                inp["slippage_per_side"] = parts[idx + 1]
                if idx + 2 < len(parts) and parts[idx + 2] and parts[idx + 2] != "Starting account":
                    inp["slippage_note"] = parts[idx + 2]
            if p == "Starting account":
                inp["starting_account"] = parts[idx + 1]
                if idx + 2 < len(parts):
                    inp["starting_account_note"] = parts[idx + 2]
            if p.startswith("Risk per trade"):
                inp["risk_per_trade"] = parts[idx + 1]
                if idx + 2 < len(parts):
                    inp["risk_per_trade_note"] = parts[idx + 2]
                inp["risk_per_trade_label"] = p
    out["input"] = inp

    results: dict = {}
    for line in lines[lines.index("Results") + 1 :]:
        if line.startswith("How far to trust") or line.startswith("Trade-by-trade"):
            break
        if not line.strip():
            continue
        parts = next(csv.reader([line]))
        if len(parts) >= 2 and parts[0]:
            results[parts[0]] = parts[1]
    out["results"] = results

    extra: dict = {}
    for line in lines:
        if line.startswith("Trade-by-trade maximum drawdown"):
            parts = next(csv.reader([line]))
            extra["trade_by_trade_max_drawdown_R"] = parts[1]
            extra["trade_by_trade_max_drawdown_note"] = parts[2] if len(parts) > 2 else ""
    out["extra"] = extra

    caveats: list[str] = []
    for line in lines[lines.index("How far to trust this") + 1 :]:
        if line == "Risk per trade":
            break
        if not line.strip():
            continue
        text = next(csv.reader([line]))[0].strip()
        if text.startswith("$100k start"):
            break
        if text:
            caveats.append(text)
    out["caveats"] = caveats

    risk_rows: list[dict] = []
    for idx, line in enumerate(lines):
        if line.startswith("Risk per trade,Ending account"):
            header = next(csv.reader([line]))
            for line2 in lines[idx + 1 :]:
                if not line2.strip():
                    continue
                if line2.startswith('"Source:') or line2.startswith("Source:"):
                    out["risk_table_source"] = next(csv.reader([line2]))[0]
                    break
                parts = next(csv.reader([line2]))
                if not parts[0]:
                    continue
                risk_rows.append(dict(zip(header, parts)))
            break
    out["risk_table"] = risk_rows

    for line in lines:
        if line.startswith('"$100k start') or line.startswith("$100k start"):
            out["risk_table_intro"] = next(csv.reader([line]))[0]
            break

    rules_lines = (DATA / "rules.csv").read_text(encoding="utf-8").splitlines()
    out["rules_meta"] = {
        "title": rules_lines[0],
        "blurb": next(csv.reader([rules_lines[1]]))[0],
    }
    header_idx = next(i for i, l in enumerate(rules_lines) if l.startswith("#,Group,Rule"))
    rules: list[dict] = []
    for row in csv.DictReader(rules_lines[header_idx:]):
        n = (row.get("#") or "").strip()
        if not n.isdigit():
            break
        rules.append(
            {
                "n": int(n),
                "group": row["Group"],
                "rule": row["Rule"],
                "value": (row.get("Value") or "").strip(),
            }
        )
    out["rules"] = rules

    notes: list[str] = []
    in_notes = False
    for line in rules_lines:
        if line.strip() == "Notes":
            in_notes = True
            continue
        if in_notes and line.strip():
            notes.append(next(csv.reader([line]))[0])
    out["rules_notes"] = notes

    out["monthly"] = read_table("monthly.csv")
    out["half_years"] = read_table("half-years.csv")

    comparison = []
    for row in read_table("comparison.csv"):
        rs = row.get("Rule set", "")
        if not rs or rs.startswith("Simulation"):
            continue
        comparison.append(row)
    out["comparison"] = comparison
    for line in (DATA / "comparison.csv").read_text(encoding="utf-8").splitlines():
        if line.startswith("Simulation outputs"):
            out["comparison_note"] = line
            break

    out["version_history"] = read_table("version_history.csv")

    with open(DATA / "best_and_worst.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header = ["kind"] + rows[0][1:]
    bw: list[dict] = []
    for r in rows[1:]:
        if not r:
            continue
        if r[0] in ("Best", "Worst"):
            padded = r + [""] * (len(header) - len(r))
            bw.append(dict(zip(header, padded[: len(header)])))
        elif r[0].startswith("R after"):
            out["best_worst_note"] = r[0]
    out["best_and_worst"] = bw

    trade_cols = [
        "Entry date",
        "Symbol",
        "Daily setup",
        "Fill time (ET)",
        "Kept overnight",
        "Exit date",
        "Exit",
        "Days held",
        "R",
    ]
    with open(DATA / "trades.csv", newline="", encoding="utf-8") as f:
        out["trades"] = [{k: row.get(k, "") for k in trade_cols} for row in csv.DictReader(f)]

    out["disclaimer"] = {
        "title": "How far to trust this",
        "hypothetical": (
            "This is a simulated backtest, not a record of actual trading. "
            "Past results do not guarantee future results. "
            "Nothing on this page is investment advice."
        ),
    }
    return out


def main() -> None:
    out = scrub_tree(build())
    path = DATA / "backtest.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    blob = path.read_text(encoding="utf-8")
    if re.search(r"cross[\s_-]*back", blob, flags=re.I):
        raise SystemExit("backtest.json still contains a crossback substring after scrub")
    print(
        f"Wrote {path} ({path.stat().st_size} bytes) — "
        f"{len(out['rules'])} rules, {len(out['monthly'])} months, {len(out['trades'])} trades"
    )


if __name__ == "__main__":
    main()
