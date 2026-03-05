"""日別USD損益算出モジュール。

parsed_confirmations.jsonlからアカウント別・日別の損益を集計する。
"""

import json
import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


def compute_daily_pnl(input_path: Path, output_path: Path) -> int:
    """日別USD損益を算出してJSONLファイルに出力する。

    Args:
        input_path: 入力JSONLファイルのパス。
        output_path: 出力JSONLファイルのパス。

    Returns:
        出力したレコード数。
    """
    daily: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)

    with input_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("currency") != "USD":
                continue
            account_summary = record.get("account_summary")
            if account_summary is None:
                logger.warning("account_summaryが存在しないレコードをスキップ: %s", record.get("account_no"))
                continue

            date = record["report_date"].split(" ")[0]
            account_no = record["account_no"]
            deals = [d for d in record.get("deals", []) if d.get("type") != "balance"]

            commission = round(sum(d["commission"] + d["fee"] for d in deals), 2)
            swap = round(sum(d["swap"] for d in deals), 2)
            profit = round(sum(d["profit"] for d in deals), 2)

            daily[date][account_no] = {
                "deposit_withdrawal": account_summary["deposit_withdrawal"],
                "commission": commission,
                "swap": swap,
                "profit": profit,
                "balance": account_summary["balance"],
            }

    sorted_dates = sorted(daily.keys(), reverse=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for date in sorted_dates:
            accounts = daily[date]
            total = {
                "deposit_withdrawal": round(sum(a["deposit_withdrawal"] for a in accounts.values()), 2),
                "commission": round(sum(a["commission"] for a in accounts.values()), 2),
                "swap": round(sum(a["swap"] for a in accounts.values()), 2),
                "profit": round(sum(a["profit"] for a in accounts.values()), 2),
                "balance": round(sum(a["balance"] for a in accounts.values()), 2),
            }
            row = {
                "date": date,
                "accounts": accounts,
                "total": total,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    count = len(sorted_dates)
    logger.info("日別損益を%d件出力しました: %s", count, output_path)
    return count
