"""IC Markets Daily Confirmation パーサーのテスト。"""

import json

import pytest

from gmail_automation.parser import (
    AccountSummary,
    Deal,
    DealsSummary,
    ParsedConfirmation,
    ParserError,
    Position,
    PositionsSummary,
    _parse_account_summary,
    _parse_deals,
    _parse_number,
    _parse_positions,
    parse_daily_confirmation,
    parse_jsonl_file,
)


# ---------------------------------------------------------------------------
# テスト用HTMLフィクスチャ
# ---------------------------------------------------------------------------

SAMPLE_HTML = """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head><title>Daily Confirmation</title></head>
<body>
<div align="center">
<div style="font: 20pt Times New Roman"><b>Raw Trading Ltd</b></div><br>
<table cellspacing="1" cellpadding="3" border="0">
<tr align="left">
    <td colspan="2">A/C No: <b>7383943</b></td>
    <td colspan="6">Name: <b>Aya Koresawa</b></td>
    <td colspan="3">Currency: <b>USD</b></td>
    <td colspan="2" align="right"><b>2026.03.04 23:59</b></td>
</tr>

<tr align="left"><td colspan="14"><b>Deals:</b></td></tr>
<tr align="center" bgcolor="#C0C0C0">
<td nowrap align="left">&nbsp;&nbsp;&nbsp;Open Time</td>
<td>Ticket</td><td>Type</td><td>Size</td><td>Item</td>
<td>Price</td><td>Order</td><td colspan="2">Comment</td>
<td>Entry</td><td>Commission</td><td>Fee</td><td>Swap</td><td>Profit</td>
</tr>

<tr align=right bgcolor=#FFFFFF>
<td class=msdate align=left nowrap>2026.03.04 11:02:03</td>
<td>876526662</td><td>buy</td><td class=mspt>0.61</td>
<td>XAUUSD</td><td style="mso-number-format:0\\.00;">5164.10</td>
<td>4373841720</td><td colspan=2>My Telegram:@Thangforex</td>
<td>in</td><td class=mspt>-2.14</td><td class=mspt>0.00</td>
<td class=mspt>0.00</td><td class=mspt>0.00</td>
</tr>

<tr align=right bgcolor=#E0E0E0>
<td class=msdate align=left nowrap>2026.03.04 11:03:40</td>
<td>876527768</td><td>sell</td><td class=mspt>0.61</td>
<td>XAUUSD</td><td style="mso-number-format:0\\.00;">5167.50</td>
<td>4373842910</td><td colspan=2>My Telegram:@Thangforex</td>
<td>out</td><td class=mspt>-2.14</td><td class=mspt>0.00</td>
<td class=mspt>0.00</td><td class=mspt>207.40</td>
</tr>

<tr align=right>
<td colspan=10>&nbsp;</td>
<td class="mspt">-8.56</td><td class="mspt">0.00</td>
<td class="mspt">0.00</td><td class="mspt">261.69</td>
</tr>

<tr align=right>
<td colspan=11>&nbsp;</td>
<td colspan=2 align=right title="Commission + Swap + Profit"><b>Closed P/L:</b></td>
<td colspan=1 align=right class="mspt"><b>253.13</b></td>
</tr>
<tr align=right>
<td colspan=11>&nbsp;</td>
<td colspan=2 align=right><b>Deposit/Withdrawal:</b></td>
<td colspan=1 align=right class="mspt"><b>0.00</b></td>
</tr>
<tr align=right>
<td colspan=11>&nbsp;</td>
<td colspan=2 align=right><b>Credit Facility:</b></td>
<td colspan=1 align=right class="mspt"><b>0.00</b></td>
</tr>
<tr align=right>
<td colspan=11>&nbsp;</td>
<td colspan=2 align=right><b>Round Commission:</b></td>
<td colspan=1 align=right class="mspt"><b>0.00</b></td>
</tr>
<tr align=right>
<td colspan=11>&nbsp;</td>
<td colspan=2 align=right><b>Instant Commission:</b></td>
<td colspan=1 align=right class="mspt"><b>-8.56</b></td>
</tr>
<tr align=right>
<td colspan=11>&nbsp;</td>
<td colspan=2 align=right><b>Fee:</b></td>
<td colspan=1 align=right class="mspt"><b>0.00</b></td>
</tr>
<tr align=right>
<td colspan=11>&nbsp;</td>
<td colspan=2 align=right><b>Additional Operations:</b></td>
<td colspan=1 align=right class="mspt"><b>0.00</b></td>
</tr>
<tr align=right>
<td colspan=11>&nbsp;</td>
<td colspan=2 align=right><b>Total:</b></td>
<td colspan=1 align=right class="mspt"><b>253.13</b></td>
</tr>

<tr align="left"><td colspan="14">&nbsp;</td></tr>
<tr align="left"><td colspan="14"><b>Positions:</b></td></tr>
<tr align="center" bgcolor="#C0C0C0">
<td nowrap align="left">&nbsp;&nbsp;&nbsp;Open Time</td>
<td>Ticket</td><td>Type</td><td>Size</td><td>Item</td>
<td>Price</td><td>S / L</td><td>T / P</td>
<td colspan="2" nowrap>Market Price</td><td>Swap</td>
<td colspan="3" nowrap>Profit</td>
</tr>
<tr align=right><td colspan=14 nowrap align=center>No transactions</td></tr>

<tr align="right">
    <td colspan="10">&nbsp;</td>
    <td class="mspt">0.00</td><td colspan="1">&nbsp;</td>
    <td class="mspt">0.00</td>
</tr>
<tr>
<td colspan="11">&nbsp;</td><td colspan="2" align="right"><b>Floating P/L:</b></td>
<td colspan="2" align="right" class="mspt"><b>0.00</b></td>
</tr>

<tr align="left"><td colspan="14"><b>Working Orders:</b></td></tr>
<tr align="center" bgcolor="#C0C0C0">
<td nowrap align="left">&nbsp;&nbsp;&nbsp;Open Time</td>
<td>Ticket</td><td>Type</td><td>Size</td><td>Item</td>
<td>Price</td><td>S / L</td><td>T / P</td>
<td colspan="2" nowrap>Market Price</td><td colspan="4">Comment</td>
</tr>
<tr align=right><td colspan=14 nowrap align=center>No transactions</td></tr>

<tr><td colspan=14>&nbsp;</td></tr>
<tr><td colspan=14 align=left><b>A/C Summary:</b></td></tr>
<tr>
<td colspan=3 align=left>Closed Trade P/L:</td>
<td colspan=2 align=right class=mspt>253.13</td>
<td colspan=3>&nbsp;</td>
<td colspan=3 align=right>Previous Ledger Balance:</td>
<td colspan=3 align=right class=mspt>29 717.45</td>
</tr>
<tr>
<td colspan=3 align=left>Deposit/Withdrawal:</td>
<td colspan=2 align=right class=mspt>0.00</td>
<td colspan=3>&nbsp;</td>
<td colspan=3 align=right>Previous Equity:</td>
<td colspan=3 align=right class=mspt>29 717.45</td>
</tr>
<tr>
<td colspan=3 align=left>Total Credit Facility:</td>
<td colspan=2 align=right class=mspt>0.00</td>
<td colspan=3>&nbsp;</td>
<td colspan=3 align=right>Balance:</td>
<td colspan=3 align=right class=mspt>29 970.58</td>
</tr>
<tr>
<td colspan=3 align=left>Round Commission:</td>
<td colspan=2 align=right class=mspt>0.00</td>
<td colspan=3>&nbsp;</td>
<td colspan=3 align=right>Equity:</td>
<td colspan=3 align=right class=mspt>29 970.58</td>
</tr>
<tr>
<td colspan=3 align=left>Instant Commission:</td>
<td colspan=2 align=right class=mspt>-8.56</td>
<td colspan=3>&nbsp;</td>
<td colspan=3 align=right>Floating P/L:</td>
<td colspan=3 align=right class=mspt>0.00</td>
</tr>
<tr>
<td colspan=3 align=left>Additional Operations:</td>
<td colspan=2 align=right class=mspt>0.00</td>
<td colspan=3>&nbsp;</td>
<td colspan=3 align=right>Margin Requirements:</td>
<td colspan=3 align=right class=mspt>0.00</td>
</tr>
<tr>
<td colspan=3 align=left>Fee:</td>
<td colspan=2 align=right class=mspt>0.00</td>
<td colspan=3>&nbsp;</td>
<td colspan=3 align=right>Available Margin:</td>
<td colspan=3 align=right class=mspt>29 970.58</td>
</tr>
<tr>
<td colspan=8>&nbsp;</td>
<td colspan=3 align=right>Total:</td>
<td colspan=3 align=right class=mspt>253.13</td>
</tr>

</table>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# TestParseNumber
# ---------------------------------------------------------------------------

class TestParseNumber:
    def test_parse_normal_number(self):
        assert _parse_number("5164.10") == 5164.10

    def test_parse_spaced_number(self):
        assert _parse_number("29 717.45") == 29717.45

    def test_parse_negative(self):
        assert _parse_number("-8.56") == -8.56

    def test_parse_empty(self):
        assert _parse_number("") == 0.0

    def test_parse_nbsp(self):
        assert _parse_number("\xa0") == 0.0
        assert _parse_number("&nbsp;") == 0.0

    def test_parse_invalid_raises(self):
        with pytest.raises(ParserError):
            _parse_number("abc")


# ---------------------------------------------------------------------------
# TestParseDeals
# ---------------------------------------------------------------------------

class TestParseDeals:
    def test_parse_deals_with_data(self):
        result = parse_daily_confirmation(SAMPLE_HTML)
        deals = result["deals"]

        assert len(deals) == 2

        assert deals[0]["ticket"] == "876526662"
        assert deals[0]["type"] == "buy"
        assert deals[0]["size"] == 0.61
        assert deals[0]["item"] == "XAUUSD"
        assert deals[0]["price"] == 5164.10
        assert deals[0]["entry"] == "in"
        assert deals[0]["commission"] == -2.14
        assert deals[0]["profit"] == 0.00

        assert deals[1]["ticket"] == "876527768"
        assert deals[1]["type"] == "sell"
        assert deals[1]["entry"] == "out"
        assert deals[1]["profit"] == 207.40

    def test_parse_deals_summary(self):
        result = parse_daily_confirmation(SAMPLE_HTML)
        summary = result["deals_summary"]

        assert summary is not None
        assert summary["closed_pl"] == 253.13
        assert summary["instant_commission"] == -8.56
        assert summary["total"] == 253.13

    def test_parse_deals_no_transactions(self):
        html = """<html><body><table>
        <tr><td colspan="14"><b>Deals:</b></td></tr>
        <tr align="center" bgcolor="#C0C0C0"><td>Header</td></tr>
        <tr><td colspan=14 align=center>No transactions</td></tr>
        <tr><td colspan="14"><b>Positions:</b></td></tr>
        </table></body></html>"""
        result = parse_daily_confirmation(html)
        assert result["deals"] == []


# ---------------------------------------------------------------------------
# TestParsePositions
# ---------------------------------------------------------------------------

class TestParsePositions:
    def test_parse_positions_no_transactions(self):
        result = parse_daily_confirmation(SAMPLE_HTML)
        assert result["positions"] == []

    def test_parse_positions_summary(self):
        result = parse_daily_confirmation(SAMPLE_HTML)
        summary = result["positions_summary"]
        assert summary is not None
        assert summary["floating_pl"] == 0.00


# ---------------------------------------------------------------------------
# TestParseAccountSummary
# ---------------------------------------------------------------------------

class TestParseAccountSummary:
    def test_parse_account_summary(self):
        result = parse_daily_confirmation(SAMPLE_HTML)
        ac = result["account_summary"]

        assert ac is not None
        assert ac["closed_trade_pl"] == 253.13
        assert ac["deposit_withdrawal"] == 0.00
        assert ac["total_credit_facility"] == 0.00
        assert ac["round_commission"] == 0.00
        assert ac["instant_commission"] == -8.56
        assert ac["additional_operations"] == 0.00
        assert ac["fee"] == 0.00
        assert ac["previous_ledger_balance"] == 29717.45
        assert ac["previous_equity"] == 29717.45
        assert ac["balance"] == 29970.58
        assert ac["equity"] == 29970.58
        assert ac["floating_pl"] == 0.00
        assert ac["margin_requirements"] == 0.00
        assert ac["available_margin"] == 29970.58
        assert ac["total"] == 253.13


# ---------------------------------------------------------------------------
# TestParseDailyConfirmation
# ---------------------------------------------------------------------------

class TestParseDailyConfirmation:
    def test_full_parse(self):
        result = parse_daily_confirmation(SAMPLE_HTML)

        assert result["account_no"] == "7383943"
        assert result["name"] == "Aya Koresawa"
        assert result["currency"] == "USD"
        assert result["report_date"] == "2026.03.04 23:59"
        assert len(result["deals"]) == 2
        assert result["deals_summary"] is not None
        assert result["positions"] == []
        assert result["positions_summary"] is not None
        assert result["account_summary"] is not None

    def test_parse_validates_with_pydantic(self):
        result = parse_daily_confirmation(SAMPLE_HTML)
        confirmation = ParsedConfirmation(
            message_id="test_id",
            date="2026-03-04",
            **result,
        )
        assert confirmation.account_no == "7383943"
        assert len(confirmation.deals) == 2


# ---------------------------------------------------------------------------
# TestParseJsonlFile
# ---------------------------------------------------------------------------

class TestParseJsonlFile:
    def test_parse_jsonl_file(self, tmp_path):
        input_file = tmp_path / "input.jsonl"
        output_file = tmp_path / "output.jsonl"

        record = {
            "message_id": "msg_001",
            "date": "2026-03-04",
            "html_body": SAMPLE_HTML,
        }
        input_file.write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        count = parse_jsonl_file(input_file, output_file)
        assert count == 1

        with output_file.open("r", encoding="utf-8") as f:
            output_record = json.loads(f.readline())

        assert output_record["message_id"] == "msg_001"
        assert output_record["account_no"] == "7383943"
        assert len(output_record["deals"]) == 2

    def test_parse_jsonl_file_not_found(self, tmp_path):
        count = parse_jsonl_file(
            tmp_path / "nonexistent.jsonl", tmp_path / "output.jsonl"
        )
        assert count == 0

    def test_parse_jsonl_file_empty_html(self, tmp_path):
        input_file = tmp_path / "input.jsonl"
        output_file = tmp_path / "output.jsonl"

        record = {"message_id": "msg_002", "date": "2026-03-04", "html_body": ""}
        input_file.write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        count = parse_jsonl_file(input_file, output_file)
        assert count == 0
