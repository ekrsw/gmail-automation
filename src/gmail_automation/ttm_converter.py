"""TTM CSV→JSON変換モジュール。

三菱UFJ銀行のTTM（仲値）CSVファイルをJSON形式に変換する。
"""

import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MONTH_NAMES = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]
SUMMARY_LABELS = {"月中平均": "average", "月中最高": "high", "月中最低": "low"}


def convert_ttm_csv(input_path: Path, output_path: Path, year: int) -> Path:
    """TTM CSVファイルをJSON形式に変換する。

    Args:
        input_path: 入力CSVファイルパス。
        output_path: 出力JSONファイルパス。
        year: 対象年。

    Returns:
        出力ファイルパス。
    """
    rates: dict[str, float] = {}
    monthly_summary: dict[str, dict[str, float]] = {}

    with input_path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        month_indices = {i: idx for idx, name in enumerate(MONTH_NAMES) for i in range(len(header)) if header[i] == name}
        # header[0]は"日 付", header[1]〜header[12]が1月〜12月
        # month_indicesは不要、直接インデックスで処理する

        for row in reader:
            label = row[0].strip()

            if label in SUMMARY_LABELS:
                key = SUMMARY_LABELS[label]
                for month_num in range(1, 13):
                    val = row[month_num].strip() if month_num < len(row) else ""
                    if val:
                        month_key = str(month_num)
                        if month_key not in monthly_summary:
                            monthly_summary[month_key] = {}
                        monthly_summary[month_key][key] = float(val)
            else:
                day = int(label)
                for month_num in range(1, 13):
                    val = row[month_num].strip() if month_num < len(row) else ""
                    if val:
                        date_str = f"{year}-{month_num:02d}-{day:02d}"
                        rates[date_str] = float(val)

    sorted_rates = dict(sorted(rates.items()))

    result = {
        "year": year,
        "rates": sorted_rates,
        "monthly_summary": monthly_summary,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info("TTM変換完了: %d件のレート, %d件の月次サマリー", len(rates), len(monthly_summary))
    return output_path
