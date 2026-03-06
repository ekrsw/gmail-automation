"""日別USD損益の円換算モジュール。

daily_pnl.jsonlのUSD損益をTTMレートで円換算し、日別・月計・年計を算出する。
"""

import json
import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_ttm_rates(ttm_path: Path) -> dict[str, float]:
    """TTM JSONファイルからレートを読み込む。

    Args:
        ttm_path: TTM JSONファイルのパス。

    Returns:
        日付文字列（YYYY-MM-DD）をキー、レートを値とする辞書。
    """
    with ttm_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["rates"]


def _convert_date_format(date_str: str) -> str:
    """日付フォーマットを変換する。

    Args:
        date_str: "YYYY.MM.DD"形式の日付文字列。

    Returns:
        "YYYY-MM-DD"形式の日付文字列。
    """
    return date_str.replace(".", "-")


def _round_jpy(value: float) -> int:
    """円換算値を整数に丸める。

    Args:
        value: 円換算値。

    Returns:
        四捨五入した整数値。
    """
    return round(value)


def convert_daily_pnl_to_jpy(
    pnl_path: Path, ttm_path: Path, output_path: Path,
) -> int:
    """日別USD損益を円換算し、日別・月計・年計を出力する。

    Args:
        pnl_path: daily_pnl.jsonlのパス。
        ttm_path: TTM JSONファイルのパス。
        output_path: 出力JSONファイルのパス。

    Returns:
        出力した日別レコード数。
    """
    rates = _load_ttm_rates(ttm_path)

    daily_records = []
    with pnl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            daily_records.append(json.loads(line))

    daily_records.sort(key=lambda r: r["date"])

    fields = ["deposit_withdrawal", "commission", "swap", "profit"]
    daily_jpy = []
    monthly_data: dict[str, dict[str, int]] = defaultdict(lambda: {k: 0 for k in fields})
    yearly_data: dict[str, int] = {k: 0 for k in fields}

    for record in daily_records:
        date_dot = record["date"]
        date_iso = _convert_date_format(date_dot)
        rate = rates.get(date_iso)

        if rate is None:
            logger.warning("TTMレートが見つかりません: %s（スキップ）", date_iso)
            continue

        total_usd = record["total"]

        # 日別の全アカウント合算をまとめて換算
        day_jpy = {}
        for field in fields:
            day_jpy[field] = _round_jpy(total_usd[field] * rate)

        day_jpy["balance"] = _round_jpy(total_usd["balance"] * rate)
        day_jpy["rate"] = rate

        # アカウント別の換算
        accounts_jpy = {}
        for account_no, acct_usd in record["accounts"].items():
            acct_jpy = {}
            for field in fields:
                acct_jpy[field] = _round_jpy(acct_usd[field] * rate)
            acct_jpy["balance"] = _round_jpy(acct_usd["balance"] * rate)
            accounts_jpy[account_no] = acct_jpy

        daily_jpy.append({
            "date": date_dot,
            "rate": rate,
            "accounts": accounts_jpy,
            "total": day_jpy,
        })

        # 月計に加算
        month_key = date_dot[:7]  # "YYYY.MM"
        for field in fields:
            monthly_data[month_key][field] += day_jpy[field]

        # 年計に加算
        for field in fields:
            yearly_data[field] += day_jpy[field]

    daily_jpy.sort(key=lambda r: r["date"], reverse=True)

    monthly_summary = []
    for month_key in sorted(monthly_data.keys()):
        monthly_summary.append({
            "month": month_key,
            **monthly_data[month_key],
        })

    result = {
        "daily": daily_jpy,
        "monthly": monthly_summary,
        "yearly": yearly_data,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    count = len(daily_jpy)
    logger.info("円換算損益を出力しました: 日別%d件, 月計%d件", count, len(monthly_summary))
    return count
