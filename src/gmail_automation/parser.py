"""IC Markets Daily Confirmation パーサーモジュール。

HTMLテーブル形式の取引レポートから
Deals、Positions、A/C Summaryを構造化データとして抽出する。
"""

import json
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ParserError(Exception):
    """パーサー処理中のエラー。"""


class Deal(BaseModel):
    open_time: str
    ticket: str
    type: str
    size: float
    item: str
    price: float
    order: str
    comment: str = ""
    entry: str
    commission: float
    fee: float
    swap: float
    profit: float


class DealsSummary(BaseModel):
    closed_pl: float
    deposit_withdrawal: float
    credit_facility: float
    round_commission: float
    instant_commission: float
    fee: float
    additional_operations: float
    total: float


class Position(BaseModel):
    open_time: str
    ticket: str
    type: str
    size: float
    item: str
    price: float
    sl: float
    tp: float
    market_price: float
    swap: float
    profit: float


class PositionsSummary(BaseModel):
    floating_pl: float


class AccountSummary(BaseModel):
    closed_trade_pl: float
    deposit_withdrawal: float
    total_credit_facility: float
    round_commission: float
    instant_commission: float
    additional_operations: float
    fee: float
    previous_ledger_balance: float
    previous_equity: float
    balance: float
    equity: float
    floating_pl: float
    margin_requirements: float
    available_margin: float
    total: float


class ParsedConfirmation(BaseModel):
    message_id: str
    date: str
    account_no: str
    name: str
    currency: str
    report_date: str
    deals: list[Deal] = []
    deals_summary: DealsSummary | None = None
    positions: list[Position] = []
    positions_summary: PositionsSummary | None = None
    account_summary: AccountSummary | None = None


def _parse_number(text: str) -> float:
    """数値文字列をfloatに変換する。

    スペース区切り（`29 717.45`）や `&nbsp;` を含む文字列に対応。

    Args:
        text: 数値文字列。

    Returns:
        変換後のfloat値。空文字列の場合は0.0。
    """
    cleaned = text.replace("\xa0", "").replace("&nbsp;", "").replace(" ", "").strip()
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError as e:
        raise ParserError(f"数値変換失敗: '{text}'") from e


def _get_cell_text(td: Tag) -> str:
    """tdタグからテキストを取得し、前後の空白を除去する。"""
    return td.get_text(strip=True)


def _find_section_rows(soup: BeautifulSoup, label: str) -> list[Tag]:
    """見出しラベルを起点に次セクションまでの<tr>を収集する。

    Args:
        soup: パース済みのBeautifulSoupオブジェクト。
        label: セクション見出し（例: "Deals:"）。

    Returns:
        セクション内の<tr>タグのリスト。見出し行は含まない。
    """
    heading_td = soup.find("b", string=re.compile(re.escape(label)))
    if heading_td is None:
        return []

    heading_tr = heading_td.find_parent("tr")
    if heading_tr is None:
        return []

    _section_headings = {
        "Orders:", "Deals:", "Positions:", "Working Orders:", "A/C Summary:",
    }

    rows: list[Tag] = []
    for sibling in heading_tr.find_next_siblings("tr"):
        # 次のセクション見出しに到達したら終了
        bold = sibling.find("b")
        if bold:
            bold_text = bold.get_text(strip=True)
            if bold_text in _section_headings and bold_text != label:
                break
        rows.append(sibling)

    return rows


def _parse_header(soup: BeautifulSoup) -> dict:
    """A/C No, Name, Currency, レポート日付を抽出する。"""
    result = {
        "account_no": "",
        "name": "",
        "currency": "",
        "report_date": "",
    }

    # A/C No, Name, Currency, 日付を含むtr行を探す
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if text.startswith("A/C No:"):
            bold = td.find("b")
            if bold:
                result["account_no"] = bold.get_text(strip=True)
        elif text.startswith("Name:"):
            bold = td.find("b")
            if bold:
                result["name"] = bold.get_text(strip=True)
        elif text.startswith("Currency:"):
            bold = td.find("b")
            if bold:
                result["currency"] = bold.get_text(strip=True)

    # レポート日付はヘッダー行の最後のtdのbold
    header_tds = soup.find_all("td", attrs={"colspan": "2", "align": "right"})
    for td in header_tds:
        bold = td.find("b")
        if bold:
            date_text = bold.get_text(strip=True)
            if re.match(r"\d{4}\.\d{2}\.\d{2}", date_text):
                result["report_date"] = date_text
                break

    return result


def _is_data_row(row: Tag) -> bool:
    """データ行かどうかを判定する（ヘッダー行・空行を除外）。"""
    bgcolor = row.get("bgcolor", "")
    if isinstance(bgcolor, list):
        bgcolor = bgcolor[0] if bgcolor else ""
    return bgcolor.upper() in ("#FFFFFF", "#E0E0E0")


def _parse_deals(rows: list[Tag]) -> tuple[list[Deal], DealsSummary | None]:
    """Dealsセクションの行をパースする。"""
    deals: list[Deal] = []
    summary_data: dict[str, float] = {}

    for row in rows:
        # ヘッダー行（bgcolor=#C0C0C0）はスキップ
        bgcolor = row.get("bgcolor", "")
        if isinstance(bgcolor, list):
            bgcolor = bgcolor[0] if bgcolor else ""
        if bgcolor.upper() == "#C0C0C0":
            continue

        tds = row.find_all("td")
        if not tds:
            continue

        # "No transactions" チェック
        full_text = row.get_text(strip=True)
        if "No transactions" in full_text:
            continue

        # サマリ行の判定: bold テキストで "P/L:" 等を含む行
        bold = row.find("b")
        if bold:
            bold_text = bold.get_text(strip=True)
            label_map = {
                "Closed P/L:": "closed_pl",
                "Deposit/Withdrawal:": "deposit_withdrawal",
                "Credit Facility:": "credit_facility",
                "Round Commission:": "round_commission",
                "Instant Commission:": "instant_commission",
                "Fee:": "fee",
                "Additional Operations:": "additional_operations",
                "Total:": "total",
            }
            if bold_text in label_map:
                # 最後のtdのboldから値を取得
                last_bold = tds[-1].find("b")
                if last_bold:
                    summary_data[label_map[bold_text]] = _parse_number(
                        last_bold.get_text(strip=True)
                    )
                continue

        # 集計行（commission, fee, swap, profitの合計行）
        if _is_data_row(row):
            # データ行: 14列（colspanを考慮してtd数ではなく実テキストで判定）
            texts = [_get_cell_text(td) for td in tds]
            # Deal行は最低10個のtdを持つ
            if len(tds) >= 10:
                try:
                    deal = Deal(
                        open_time=texts[0],
                        ticket=texts[1],
                        type=texts[2],
                        size=_parse_number(texts[3]),
                        item=texts[4],
                        price=_parse_number(texts[5]),
                        order=texts[6],
                        comment=texts[7] if len(tds) > 10 else "",
                        entry=texts[8] if len(tds) > 10 else texts[7],
                        commission=_parse_number(
                            texts[9] if len(tds) > 10 else texts[8]
                        ),
                        fee=_parse_number(
                            texts[10] if len(tds) > 10 else texts[9]
                        ),
                        swap=_parse_number(
                            texts[11] if len(tds) > 10 else texts[10]
                        ),
                        profit=_parse_number(
                            texts[12] if len(tds) > 10 else texts[11]
                        ),
                    )
                    deals.append(deal)
                except (IndexError, ParserError) as e:
                    logger.warning("Deal行のパースに失敗: %s", e)

    deals_summary = DealsSummary(**summary_data) if summary_data else None
    return deals, deals_summary


def _parse_positions(rows: list[Tag]) -> tuple[list[Position], PositionsSummary | None]:
    """Positionsセクションの行をパースする。"""
    positions: list[Position] = []
    floating_pl: float | None = None

    for row in rows:
        bgcolor = row.get("bgcolor", "")
        if isinstance(bgcolor, list):
            bgcolor = bgcolor[0] if bgcolor else ""
        if bgcolor.upper() == "#C0C0C0":
            continue

        tds = row.find_all("td")
        if not tds:
            continue

        full_text = row.get_text(strip=True)
        if "No transactions" in full_text:
            continue

        # Floating P/L サマリ行
        bold = row.find("b")
        if bold and "Floating P/L:" in bold.get_text(strip=True):
            last_bold = tds[-1].find("b")
            if last_bold:
                floating_pl = _parse_number(last_bold.get_text(strip=True))
            continue

        if _is_data_row(row):
            texts = [_get_cell_text(td) for td in tds]
            if len(tds) >= 10:
                try:
                    position = Position(
                        open_time=texts[0],
                        ticket=texts[1],
                        type=texts[2],
                        size=_parse_number(texts[3]),
                        item=texts[4],
                        price=_parse_number(texts[5]),
                        sl=_parse_number(texts[6]),
                        tp=_parse_number(texts[7]),
                        market_price=_parse_number(texts[8]),
                        swap=_parse_number(texts[9]),
                        profit=_parse_number(texts[10] if len(tds) > 10 else texts[9]),
                    )
                    positions.append(position)
                except (IndexError, ParserError) as e:
                    logger.warning("Position行のパースに失敗: %s", e)

    positions_summary = (
        PositionsSummary(floating_pl=floating_pl)
        if floating_pl is not None
        else None
    )
    return positions, positions_summary


def _parse_account_summary(rows: list[Tag]) -> AccountSummary | None:
    """A/C Summaryセクションをパースする。

    左右2カラムレイアウトから各項目を抽出する。
    """
    data: dict[str, float] = {}

    label_map = {
        "Closed Trade P/L:": "closed_trade_pl",
        "Deposit/Withdrawal:": "deposit_withdrawal",
        "Total Credit Facility:": "total_credit_facility",
        "Round Commission:": "round_commission",
        "Instant Commission:": "instant_commission",
        "Additional Operations:": "additional_operations",
        "Fee:": "fee",
        "Previous Ledger Balance:": "previous_ledger_balance",
        "Previous Equity:": "previous_equity",
        "Balance:": "balance",
        "Equity:": "equity",
        "Floating P/L:": "floating_pl",
        "Margin Requirements:": "margin_requirements",
        "Available Margin:": "available_margin",
        "Total:": "total",
    }

    for row in rows:
        tds = row.find_all("td")
        if not tds:
            continue

        # 各tdのテキストを走査してラベルを探す
        for i, td in enumerate(tds):
            text = _get_cell_text(td)
            if text in label_map:
                # 次のtdが値
                if i + 1 < len(tds):
                    value_text = _get_cell_text(tds[i + 1])
                    try:
                        data[label_map[text]] = _parse_number(value_text)
                    except ParserError as e:
                        logger.warning("A/C Summary値のパース失敗: %s - %s", text, e)

    if not data:
        return None

    # 欠損項目は0.0で埋める
    for key in label_map.values():
        data.setdefault(key, 0.0)

    return AccountSummary(**data)


def parse_daily_confirmation(html: str) -> dict:
    """Daily ConfirmationのHTMLをパースし辞書を返す。

    Args:
        html: Daily ConfirmationのHTML文字列。

    Returns:
        パース結果の辞書。
    """
    soup = BeautifulSoup(html, "html.parser")

    header = _parse_header(soup)

    deals_rows = _find_section_rows(soup, "Deals:")
    deals, deals_summary = _parse_deals(deals_rows)

    positions_rows = _find_section_rows(soup, "Positions:")
    positions, positions_summary = _parse_positions(positions_rows)

    ac_rows = _find_section_rows(soup, "A/C Summary:")
    account_summary = _parse_account_summary(ac_rows)

    return {
        "account_no": header["account_no"],
        "name": header["name"],
        "currency": header["currency"],
        "report_date": header["report_date"],
        "deals": [d.model_dump() for d in deals],
        "deals_summary": deals_summary.model_dump() if deals_summary else None,
        "positions": [p.model_dump() for p in positions],
        "positions_summary": (
            positions_summary.model_dump() if positions_summary else None
        ),
        "account_summary": (
            account_summary.model_dump() if account_summary else None
        ),
    }


def parse_jsonl_file(input_path: Path, output_path: Path) -> int:
    """emails.jsonlを読み込み、各行のhtml_bodyをパースしてJSONL出力する。

    Args:
        input_path: 入力JSONLファイルのパス。
        output_path: 出力JSONLファイルのパス。

    Returns:
        正常にパースされたレコード数。
    """
    from gmail_automation.converter import append_to_jsonl

    if not input_path.exists():
        logger.error("入力ファイルが見つかりません: %s", input_path)
        return 0

    success_count = 0
    error_count = 0

    with input_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning("行 %d: JSON読み込み失敗: %s", line_no, e)
                error_count += 1
                continue

            html_body = record.get("html_body", "")
            if not html_body:
                logger.debug("行 %d: html_bodyが空です", line_no)
                continue

            try:
                parsed = parse_daily_confirmation(html_body)
                parsed["message_id"] = record.get("message_id", "")
                parsed["date"] = record.get("date", "")
                append_to_jsonl(parsed, output_path)
                success_count += 1
            except (ParserError, Exception) as e:
                logger.warning("行 %d: パース失敗: %s", line_no, e)
                error_count += 1

    logger.info(
        "パース完了: 成功=%d件, エラー=%d件, 出力=%s",
        success_count,
        error_count,
        output_path,
    )
    return success_count
