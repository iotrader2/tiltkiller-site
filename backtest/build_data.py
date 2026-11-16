#!/usr/bin/env python3
"""Rebuild public backtest/data/backtest.json from private sheet exports.

Raw CSVs live in backtest/raw/ (gitignored — not shipped). Public output is only
plain-language JSON under backtest/data/.

    python3 backtest/build_data.py
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
DATA = ROOT / "data"

BANNED = re.compile(
    r"cross[\s_-]*back|\bEMA\b|\bATR\b|\bQQQ\b|\bSPY\b|\bvariant|\bversion\b",
    flags=re.I,
)


def plain_setup(s: str) -> str:
    t = (s or "").strip()
    if not t:
        return t
    if re.search(r"(?:^|\b)(?:trend\s*)?leader(?:\b|$)", t, flags=re.I) and not re.search(
        r"EMA|Undercut|Flag|Wedge|Delayed", t, flags=re.I
    ):
        return "Leader"
    if re.fullmatch(r"Leader", t, flags=re.I):
        return "Leader"
    return "Pullback"


def scrub_public_text(s: str) -> str:
    """Force plain-language public copy (no indicator / private jargon)."""
    t = s
    t = re.sub(r"Trend Leader names only", "Leaders only", t, flags=re.I)
    t = re.sub(r"\bVersion\s*\d+\.\d+\b", "the current rules", t, flags=re.I)
    t = re.sub(r"\bv\d+\.\d+\b", "", t, flags=re.I)
    t = re.sub(
        r"Pattern names not below all of the 10 EMA, 20 EMA and 50-day average",
        "Pullbacks that stay in an overall uptrend",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"Pattern names:\s*10 EMA > 20 EMA > 50-day average",
        "Pullbacks only in strong uptrends",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"Pattern names above the daily 20 EMA",
        "Pullbacks in a short-term uptrend",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"Many months have no trades \(QQQ under its 10 EMA\) or lose\.\s*Expect long flat stretches between runners\.",
        "Many months have no trades because the market was in a downtrend, or they lose. Expect long flat stretches between big winners.",
        t,
        flags=re.I,
    )
    t = re.sub(r"QQQ under its 10 EMA", "the market in a downtrend", t, flags=re.I)
    t = re.sub(
        r"No new long trades unless QQQ closed above its daily 10 EMA[^.]*\.",
        "No new long trades when the overall market looks weak.",
        t,
        flags=re.I,
    )
    t = re.sub(r"Market filter \(QQQ daily chart\)", "Market filter", t, flags=re.I)
    t = re.sub(
        r"Take a long only when the stock is stronger than QQQ since the open:[^.]*\.",
        "Only take trades when the stock is beating the market since the open.",
        t,
        flags=re.I,
    )
    t = re.sub(r"stronger than QQQ since the open", "beating the market since the open", t, flags=re.I)
    t = re.sub(
        r"comparing many variants",
        "comparing many rule sets",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"comparing many versions",
        "comparing many rule sets",
        t,
        flags=re.I,
    )
    t = re.sub(r"\bvariants?\b", "rule sets", t, flags=re.I)
    t = re.sub(r"\bversions?\b", "rule sets", t, flags=re.I)

    if re.search(
        r"Trend Leader|EMA|Moving Average Undercut|Delayed High Volume|High Tight Flag|Wedge Pop",
        t,
        flags=re.I,
    ) and len(t) < 140 and "." not in t:
        return plain_setup(t)

    t = re.sub(r"\b\d+\s*EMA\b", "trend", t, flags=re.I)
    t = re.sub(r"\bEMA\b", "trend", t, flags=re.I)
    t = re.sub(r"\bATR\b", "volatility", t, flags=re.I)
    t = re.sub(r"\bQQQ\b", "the market", t)
    t = re.sub(r"\bSPY\b", "the market", t)
    t = re.sub(r"Moving Average Undercut and Rally(?:\s*\(\d+-day\))?", "Pullback", t, flags=re.I)
    t = re.sub(r"Trend Leaders?", "Leaders", t, flags=re.I)
    t = re.sub(r"Delayed High Volume Close", "Pullback", t, flags=re.I)
    t = re.sub(r"High Tight Flag", "Pullback", t, flags=re.I)
    t = re.sub(r"Wedge Pop", "Pullback", t, flags=re.I)
    t = re.sub(r"50-day rule", "longer-term trend filter", t, flags=re.I)
    t = re.sub(r"50-day average", "longer-term trend", t, flags=re.I)
    t = re.sub(r"Crossback\s+trading\s+rules", "TiltKiller trading rules", t, flags=re.I)
    t = re.sub(r"crossback\s+rules", "trading rules", t, flags=re.I)
    t = re.sub(r"Results:\s*crossback", "Results: trading", t, flags=re.I)
    t = re.sub(r"s_ema-crossback", "pattern", t, flags=re.I)
    t = re.sub(r"cross[\s_-]*back", "pullback", t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def scrub_tree(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "Daily setup" and isinstance(v, str):
                out[k] = plain_setup(v)
            else:
                out[k] = scrub_tree(v)
        return out
    if isinstance(obj, list):
        return [scrub_tree(v) for v in obj]
    if isinstance(obj, str):
        return scrub_public_text(obj)
    return obj


def read_table(name: str) -> list[dict]:
    with open(RAW / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build() -> dict:
    if not (RAW / "results.csv").exists():
        raise SystemExit(
            f"Missing raw sheets in {RAW}. Place private CSV exports there "
            "(gitignored), then re-run build_data.py."
        )

    lines = (RAW / "results.csv").read_text(encoding="utf-8").splitlines()
    out: dict = {
        "meta": {
            "title": "TiltKiller trading rules",
            "period": "November 2023 to November 2026 (three years)",
            "r_definition": "1R is the amount you risk on a trade (what you lose if the stop hits).",
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

    # Public trust bullets (page may also hardcode these). No private/jargon strings.
    out["caveats"] = [
        "A big share of the gain comes from a few large winners. HOOD (bought 2025-05-19, about +59 times the amount risked) and MARA (bought 2023-11-27, about +43 times the amount risked) are 32% of the total.",
        "Many months have no trades because the market was in a downtrend, or they lose. Expect long flat stretches between big winners.",
        "The rules were chosen by comparing many rule sets on this same three-year period, so the figures look optimistic.",
        "Not in this simulation: late-day sells (the backtest sells at the close), trading costs, how much cash you actually need in the account, and stocks added mid-session. The name list is today’s list, so stocks that later disappeared are missing.",
        "At most 3 new trades a day — so you know your risk up front.",
    ]

    risk_rows: list[dict] = []
    for idx, line in enumerate(lines):
        if line.startswith("Risk per trade,Ending account"):
            header = next(csv.reader([line]))
            for line2 in lines[idx + 1 :]:
                if not line2.strip():
                    continue
                if line2.startswith('"Source:') or line2.startswith("Source:"):
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

    # Plain public rule summary only — never ship the private coded rule sheet.
    out["rules_meta"] = {
        "title": "TiltKiller trading rules",
        "blurb": (
            "2026-11-16. The rules as the app runs them. "
            "Tested over November 2023 to November 2026. "
            "Every change is recorded with its full results."
        ),
    }
    out["rules"] = [
        {
            "n": 1,
            "group": "Market filter",
            "rule": "Only trades when the overall market is in an uptrend. If the market looks weak, no new long alerts that day.",
            "value": "",
        },
        {
            "n": 2,
            "group": "Which names",
            "rule": "Focuses on strong, heavily traded leading stocks — Leaders and Pullbacks.",
            "value": "",
        },
        {
            "n": 3,
            "group": "Entry",
            "rule": "Buys when a stock turns back up early in the session. Alerts land in Discord from the open through 10:45 ET.",
            "value": "",
        },
        {
            "n": 4,
            "group": "Stop",
            "rule": "Every trade has a set stop. Stops aren’t guaranteed — a gap down overnight or on news can open below your stop.",
            "value": "",
        },
        {
            "n": 5,
            "group": "Exits & holds",
            "rule": "Winners can be held overnight; losers are cut quickly. Max 3 new trades a day. Long trades only.",
            "value": "",
        },
    ]
    # Private sheet notes are not shipped.
    out["rules_notes"] = []

    out["monthly"] = read_table("monthly.csv")
    out["half_years"] = read_table("half-years.csv")

    with open(RAW / "best_and_worst.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header = ["kind"] + rows[0][1:]
    bw: list[dict] = []
    for r in rows[1:]:
        if not r:
            continue
        if r[0] in ("Best", "Worst"):
            padded = r + [""] * (len(header) - len(r))
            row = dict(zip(header, padded[: len(header)]))
            if "Daily setup" in row:
                row["Daily setup"] = plain_setup(row["Daily setup"])
            bw.append(row)
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
    with open(RAW / "trades.csv", newline="", encoding="utf-8") as f:
        trades = []
        for row in csv.DictReader(f):
            item = {k: row.get(k, "") for k in trade_cols}
            item["Daily setup"] = plain_setup(item["Daily setup"])
            trades.append(item)
        out["trades"] = trades

    out["disclaimer"] = {
        "title": "How far to trust this",
        "hypothetical": (
            "This is a simulated backtest, not a record of actual trading. "
            "Past results do not guarantee future results. "
            "Nothing on this page is investment advice."
        ),
    }
    return out


def assert_clean(blob: str, path: Path) -> None:
    hits = sorted(set(m.group(0) for m in BANNED.finditer(blob)))
    if hits:
        raise SystemExit(f"{path} still contains banned terms after scrub: {hits}")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    out = scrub_tree(build())
    path = DATA / "backtest.json"
    blob = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    assert_clean(blob, path)
    path.write_text(blob, encoding="utf-8")

    # Remove any leftover public CSVs so only clean JSON ships under data/.
    for leftover in DATA.glob("*.csv"):
        leftover.unlink()
        print(f"Removed shipped CSV {leftover.name} (raw sheets live in backtest/raw/)", file=sys.stderr)

    print(
        f"Wrote {path} ({path.stat().st_size} bytes) — "
        f"{len(out['rules'])} public rules, {len(out['monthly'])} months, {len(out['trades'])} trades"
    )


if __name__ == "__main__":
    main()
