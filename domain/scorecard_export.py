from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

from domain.weekend_config import TEAM_CONFIG, team_short_name


PAGE_SIZE = landscape(A4)
PAPER = colors.HexColor("#f8f3e5")
PAPER_LIGHT = colors.HexColor("#fffdf7")
GREEN = colors.HexColor("#123f2b")
GOLD = colors.HexColor("#a98536")
GOLD_SOFT = colors.HexColor("#eadbb1")
LINE = colors.HexColor("#baab7b")
RED = colors.HexColor("#a63a37")
BLUE = colors.HexColor("#245a84")
MUTED = colors.HexColor("#687162")
INK = colors.HexColor("#172219")


def build_premium_scorecard_pdf(rounds: list[dict[str, Any]]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=PAGE_SIZE)
    for index, round_payload in enumerate(rounds):
        if index:
            pdf.showPage()
        _draw_round_page(pdf, round_payload)
    pdf.save()
    return buffer.getvalue()


def build_scorecard_round_payload(
    *,
    fixture: dict[str, Any],
    round_runtime: dict[str, Any],
    round_state: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "fixture": fixture,
        "round_runtime": round_runtime,
        "round_state": round_state,
        "result": result,
        "player_names": list(round_state.get("player_names", [])),
    }


def premium_scorecard_filename(round_payloads: list[dict[str, Any]]) -> str:
    if len(round_payloads) == 1:
        fixture_id = str(round_payloads[0].get("fixture", {}).get("id") or "round")
        return f"premium-scorecard-{fixture_id}.pdf"
    return "premium-scorecards-all-rounds.pdf"


def _draw_round_page(pdf: canvas.Canvas, payload: dict[str, Any]) -> None:
    width, height = PAGE_SIZE
    margin = 13 * mm
    rail_width = 32 * mm
    content_x = margin + rail_width + 9 * mm
    content_right = width - margin
    content_width = content_right - content_x
    card_y = margin
    card_height = height - (margin * 2)

    pdf.setFillColor(PAPER)
    pdf.rect(margin, card_y, width - (margin * 2), card_height, stroke=0, fill=1)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(0.8)
    pdf.rect(margin, card_y, width - (margin * 2), card_height, stroke=1, fill=0)

    _draw_rail(pdf, margin, card_y, rail_width, card_height)

    fixture = payload["fixture"]
    runtime = payload["round_runtime"]
    result = payload.get("result", {})
    player_names = payload.get("player_names", [])
    top_y = height - margin - 15
    _draw_header(pdf, fixture, runtime, content_x, content_right, top_y)
    _draw_player_strip(pdf, result, player_names, content_x, content_right, top_y - 48)

    score_frame = payload["round_state"].get("scores", pd.DataFrame())
    gross_front, gross_back = _build_player_gross_tables(score_frame, player_names)
    block_y = top_y - 93
    block_y = _draw_table_block(
        pdf,
        "Player Gross Scores",
        "Front / Back Nine",
        gross_front,
        gross_back,
        content_x,
        content_right,
        block_y,
    )

    match_front, match_back = _build_result_tables(result, player_names)
    block_y = _draw_table_block(
        pdf,
        _result_block_title(str(runtime.get("format_name") or result.get("format_name") or "")),
        "Team Score / Match State",
        match_front,
        match_back,
        content_x,
        content_right,
        block_y - 12,
    )

    _draw_result_band(pdf, result, content_x, content_right, block_y - 15)


def _draw_rail(pdf: canvas.Canvas, x: float, y: float, width: float, height: float) -> None:
    pdf.setFillColor(GREEN)
    pdf.rect(x, y, width, height, stroke=0, fill=1)

    crest_x = x + 15 * mm
    crest_y = y + height - 21 * mm
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1.3)
    pdf.circle(crest_x, crest_y, 10 * mm, stroke=1, fill=0)
    pdf.setFillColor(colors.HexColor("#f6e7bd"))
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawCentredString(crest_x, crest_y - 4, "RKI")

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(x + 8 * mm, crest_y - 25 * mm, "OFFICIAL")
    pdf.drawString(x + 8 * mm, crest_y - 30 * mm, "SCORECARD")

    pdf.setFont("Helvetica", 7.5)
    rail_text = ["Russell Kelly", "Invitational", "Wales 2026", "Team Kelly v", "Team Russell"]
    text_y = y + 19 * mm
    for line in rail_text:
        pdf.drawString(x + 8 * mm, text_y, line)
        text_y -= 4.1 * mm


def _draw_header(
    pdf: canvas.Canvas,
    fixture: dict[str, Any],
    runtime: dict[str, Any],
    x: float,
    right: float,
    y: float,
) -> None:
    pdf.setFillColor(GOLD)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(x, y, f"ROUND {runtime.get('round_order', fixture.get('round_order', ''))} - {fixture.get('date_label', '')}")
    pdf.setFillColor(GREEN)
    pdf.setFont("Times-Bold", 22)
    pdf.drawString(x, y - 19, str(fixture.get("title") or "Round Scorecard").upper())

    tags = [str(runtime.get("tee_label") or "Tee"), str(runtime.get("format_name") or "Format"), f"{int(runtime.get('allowance_percent') or 0)}% Allowance"]
    tag_x = right
    tag_y = y - 2
    pdf.setFont("Helvetica-Bold", 6.5)
    for tag in tags:
        label = tag.upper()
        tag_width = max(46, pdf.stringWidth(label, "Helvetica-Bold", 6.5) + 12)
        tag_x -= tag_width
        pdf.setFillColor(PAPER_LIGHT)
        pdf.setStrokeColor(GOLD)
        pdf.rect(tag_x, tag_y - 11, tag_width, 11, stroke=1, fill=1)
        pdf.setFillColor(GREEN)
        pdf.drawCentredString(tag_x + tag_width / 2, tag_y - 8, label)
        tag_y -= 14
        tag_x = right

    pdf.setStrokeColor(LINE)
    pdf.setLineWidth(0.7)
    pdf.line(x, y - 34, right, y - 34)


def _draw_player_strip(
    pdf: canvas.Canvas,
    result: dict[str, Any],
    player_names: list[str],
    x: float,
    right: float,
    y: float,
) -> None:
    gap = 5
    width = (right - x - (gap * 3)) / 4
    handicap_rows = result.get("player_handicaps")
    for index in range(4):
        player_x = x + index * (width + gap)
        team_id = _team_id_for_player_index(index)
        pdf.setFillColor(PAPER_LIGHT)
        pdf.rect(player_x, y - 24, width, 24, stroke=0, fill=1)
        pdf.setFillColor(RED if team_id == "red" else BLUE)
        pdf.rect(player_x, y - 24, 3, 24, stroke=0, fill=1)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(player_x + 7, y - 9, _text_at(player_names, index, f"Player {index + 1}"))
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 6)
        pdf.drawString(player_x + 7, y - 18, _handicap_text(handicap_rows, index))


def _draw_table_block(
    pdf: canvas.Canvas,
    title: str,
    right_label: str,
    front_data: list[list[str]],
    back_data: list[list[str]],
    x: float,
    right: float,
    y: float,
) -> float:
    pdf.setFillColor(GREEN)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(x, y, title.upper())
    pdf.drawRightString(right, y, right_label.upper())

    table_gap = 7
    table_width = (right - x - table_gap) / 2
    front = _scorecard_table(front_data, table_width)
    back = _scorecard_table(back_data, table_width)
    _, front_height = front.wrapOn(pdf, table_width, 100)
    _, back_height = back.wrapOn(pdf, table_width, 100)
    table_y = y - 5 - max(front_height, back_height)
    front.drawOn(pdf, x, table_y)
    back.drawOn(pdf, x + table_width + table_gap, table_y)
    return table_y


def _scorecard_table(data: list[list[str]], width: float) -> Table:
    row_label_width = 38
    total_width = 26
    hole_width = (width - row_label_width - total_width) / 9
    table = Table(data, colWidths=[row_label_width, *([hole_width] * 9), total_width], rowHeights=13.8)
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 5.8),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 5.8),
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 5.8),
                ("FONT", (-1, 0), (-1, -1), "Helvetica-Bold", 5.8),
                ("TEXTCOLOR", (0, 0), (-1, 0), GREEN),
                ("TEXTCOLOR", (0, 1), (0, -1), GREEN),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#efe4c5")),
                ("BACKGROUND", (-1, 0), (-1, -1), GOLD_SOFT),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.4),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ]
        )
    )
    if len(data) == 5:
        table.setStyle(
            TableStyle(
                [
                    ("TEXTCOLOR", (0, 1), (0, 2), RED),
                    ("TEXTCOLOR", (0, 3), (0, 4), BLUE),
                ]
            )
        )
    return table


def _draw_result_band(pdf: canvas.Canvas, result: dict[str, Any], x: float, right: float, y: float) -> None:
    band_height = 22
    pdf.setFillColor(GREEN)
    pdf.rect(x, y - band_height, right - x, band_height, stroke=0, fill=1)
    pdf.setFillColor(colors.HexColor("#fff3cf"))
    pdf.setFont("Helvetica-Bold", 10)
    status = str(result.get("status_text") or "Awaiting scores")
    pdf.drawString(x + 8, y - 9, _compact_status_text(status))
    pdf.setFont("Helvetica", 6.5)
    pdf.drawString(x + 8, y - 18, "Gross scores captured. Team scores and match result calculated from central scoring logic.")


def _build_player_gross_tables(score_frame: pd.DataFrame, player_names: list[str]) -> tuple[list[list[str]], list[list[str]]]:
    return (
        _build_player_gross_table(score_frame, player_names, list(range(1, 10)), "Out"),
        _build_player_gross_table(score_frame, player_names, list(range(10, 19)), "In"),
    )


def _build_player_gross_table(score_frame: pd.DataFrame, player_names: list[str], holes: list[int], total_label: str) -> list[list[str]]:
    rows = [["Hole", *[str(hole) for hole in holes], total_label]]
    for index in range(4):
        column = f"player_{index + 1}"
        values = [_score_text(score_frame, hole, column) for hole in holes]
        rows.append([_text_at(player_names, index, f"Player {index + 1}"), *values, _total_text(values)])
    return rows


def _build_result_tables(result: dict[str, Any], player_names: list[str]) -> tuple[list[list[str]], list[list[str]]]:
    format_name = str(result.get("format_name") or "")
    if format_name == "Singles":
        return _build_singles_result_tables(result, player_names)
    summary = result.get("summary_df")
    if not isinstance(summary, pd.DataFrame) or summary.empty:
        return _empty_result_tables()

    front_holes = list(range(1, 10))
    back_holes = list(range(10, 19))
    front = _build_team_result_table(summary, front_holes, "Out", format_name)
    back = _build_team_result_table(summary, back_holes, "In", format_name)
    return front, back


def _build_team_result_table(summary: pd.DataFrame, holes: list[int], total_label: str, format_name: str) -> list[list[str]]:
    red_label = team_short_name("red")
    blue_label = team_short_name("blue")
    red_values = [_summary_value(summary, hole, "team_a_best_net") for hole in holes]
    blue_values = [_summary_value(summary, hole, "team_b_best_net") for hole in holes]
    result_values = [_result_text(summary, hole) for hole in holes]
    return [
        ["Hole", *[str(hole) for hole in holes], total_label],
        [f"{red_label} Net", *red_values, _total_text(red_values)],
        [f"{blue_label} Net", *blue_values, _total_text(blue_values)],
        [_result_row_label(format_name), *result_values, _result_total_text(summary, holes, format_name)],
    ]


def _build_singles_result_tables(result: dict[str, Any], player_names: list[str]) -> tuple[list[list[str]], list[list[str]]]:
    matches = result.get("matches") or []
    if not matches:
        return _empty_result_tables()
    front_rows = [["Hole", *[str(hole) for hole in range(1, 10)], "Out"]]
    back_rows = [["Hole", *[str(hole) for hole in range(10, 19)], "In"]]
    for match in matches[:2]:
        summary = match.get("summary_df")
        if not isinstance(summary, pd.DataFrame) or summary.empty:
            continue
        left_name, right_name = list(match.get("players", ("Player A", "Player B")))
        front_rows.append([left_name, *[_summary_value(summary, hole, "left_net") for hole in range(1, 10)], _total_text([_summary_value(summary, hole, "left_net") for hole in range(1, 10)])])
        front_rows.append([right_name, *[_summary_value(summary, hole, "right_net") for hole in range(1, 10)], _total_text([_summary_value(summary, hole, "right_net") for hole in range(1, 10)])])
        front_rows.append(["Match", *[_result_text(summary, hole, left_name, right_name) for hole in range(1, 10)], _singles_match_total(summary, range(1, 10), left_name, right_name)])
        back_rows.append([left_name, *[_summary_value(summary, hole, "left_net") for hole in range(10, 19)], _total_text([_summary_value(summary, hole, "left_net") for hole in range(10, 19)])])
        back_rows.append([right_name, *[_summary_value(summary, hole, "right_net") for hole in range(10, 19)], _total_text([_summary_value(summary, hole, "right_net") for hole in range(10, 19)])])
        back_rows.append(["Match", *[_result_text(summary, hole, left_name, right_name) for hole in range(10, 19)], _singles_match_total(summary, range(10, 19), left_name, right_name)])
    return front_rows, back_rows


def _empty_result_tables() -> tuple[list[list[str]], list[list[str]]]:
    front = [["Hole", *[str(hole) for hole in range(1, 10)], "Out"], ["Match", *(["-"] * 9), "-"]]
    back = [["Hole", *[str(hole) for hole in range(10, 19)], "In"], ["Match", *(["-"] * 9), "-"]]
    return front, back


def _summary_value(summary: pd.DataFrame, hole: int, column: str) -> str:
    if column not in summary.columns:
        return "-"
    row = summary[summary["hole"].eq(hole)]
    if row.empty:
        return "-"
    return _format_number(row.iloc[0].get(column))


def _score_text(score_frame: pd.DataFrame, hole: int, column: str) -> str:
    if not isinstance(score_frame, pd.DataFrame) or score_frame.empty or column not in score_frame.columns:
        return "-"
    row = score_frame[score_frame["hole"].eq(hole)]
    if row.empty:
        return "-"
    return _format_number(row.iloc[0].get(column))


def _format_number(value: Any) -> str:
    if value is None:
        return "-"
    try:
        missing = pd.isna(value)
        if bool(missing):
            return "-"
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value == "":
        return "-"
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _total_text(values: list[str]) -> str:
    numbers = [int(value) for value in values if str(value).isdigit()]
    return str(sum(numbers)) if numbers else "-"


def _result_text(summary: pd.DataFrame, hole: int, red_value: str | None = None, blue_value: str | None = None) -> str:
    row = summary[summary["hole"].eq(hole)]
    if row.empty:
        return "-"
    value = str(row.iloc[0].get("hole_result") or "Pending")
    if value == "Halved":
        return "AS"
    if value == "Pending":
        return "-"
    if red_value and value == red_value:
        return _initial(red_value)
    if blue_value and value == blue_value:
        return _initial(blue_value)
    red_label = str(row.iloc[0].get("team_a_label") or "")
    blue_label = str(row.iloc[0].get("team_b_label") or "")
    if red_label and value == red_label:
        return team_short_name("red")[:1].upper()
    if blue_label and value == blue_label:
        return team_short_name("blue")[:1].upper()
    if value.startswith("Team Kelly") or "Kelly" in value:
        return team_short_name("red")[:1].upper()
    if value.startswith("Team Russell") or "Russell" in value:
        return team_short_name("blue")[:1].upper()
    return value[:3].upper()


def _result_total_text(summary: pd.DataFrame, holes: list[int], format_name: str) -> str:
    frame = summary[summary["hole"].isin(holes)]
    if frame.empty:
        return "-"
    if format_name == "4-Ball" and "match_delta" in frame.columns:
        balance = int(pd.to_numeric(frame["match_delta"], errors="coerce").fillna(0).sum())
        return _balance_text(balance)
    red_total = _numeric_sum(frame.get("team_a_best_net"))
    blue_total = _numeric_sum(frame.get("team_b_best_net"))
    if red_total is None or blue_total is None:
        return "-"
    if red_total == blue_total:
        return "AS"
    leader = team_short_name("red")[:1].upper() if red_total < blue_total else team_short_name("blue")[:1].upper()
    return f"{leader} +{abs(red_total - blue_total)}"


def _singles_match_total(summary: pd.DataFrame, holes: range, left_name: str, right_name: str) -> str:
    frame = summary[summary["hole"].isin(list(holes))]
    if frame.empty or "match_delta" not in frame.columns:
        return "-"
    balance = int(pd.to_numeric(frame["match_delta"], errors="coerce").fillna(0).sum())
    if balance == 0:
        return "AS"
    leader = _initial(left_name) if balance > 0 else _initial(right_name)
    return f"{leader} {abs(balance)}UP"


def _balance_text(balance: int) -> str:
    if balance == 0:
        return "AS"
    leader = team_short_name("red")[:1].upper() if balance > 0 else team_short_name("blue")[:1].upper()
    return f"{leader} {abs(balance)}UP"


def _numeric_sum(series: pd.Series | None) -> int | None:
    if series is None:
        return None
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return int(numeric.sum())


def _result_block_title(format_name: str) -> str:
    if format_name == "4-Ball":
        return "Matchplay Scorecard"
    if format_name == "Singles":
        return "Singles Matchplay"
    if format_name == "Skins":
        return "Skins Scorecard"
    return "Team Scorecard"


def _result_row_label(format_name: str) -> str:
    if format_name == "Skins":
        return "Hole"
    if format_name == "Stroke Play":
        return "Result"
    return "Match"


def _compact_status_text(value: str) -> str:
    text = value.replace("Team Kelly", team_short_name("red")).replace("Team Russell", team_short_name("blue"))
    text = text.replace(": ", " ")
    text = text.replace(" + ", " ")
    return text[:105]


def _handicap_text(player_handicaps: Any, index: int) -> str:
    if not isinstance(player_handicaps, pd.DataFrame) or player_handicaps.empty:
        return "HI - | PH -"
    row = player_handicaps[player_handicaps["Player Index"].eq(index)]
    if row.empty:
        return "HI - | PH -"
    current = row.iloc[0]
    handicap_index = current.get("Handicap Index", "-")
    playing = current.get("Playing Handicap", "-")
    try:
        handicap_text = f"{float(handicap_index):.1f}"
    except (TypeError, ValueError):
        handicap_text = "-"
    return f"HI {handicap_text} | PH {_format_number(playing)}"


def _team_id_for_player_index(index: int) -> str:
    for team_id, team in TEAM_CONFIG.items():
        if index in team["player_indices"]:
            return team_id
    return "red"


def _text_at(values: list[str], index: int, fallback: str) -> str:
    if 0 <= index < len(values) and str(values[index]).strip():
        return str(values[index])
    return fallback


def _initial(value: str) -> str:
    stripped = str(value).strip()
    return stripped[:1].upper() if stripped else "-"
