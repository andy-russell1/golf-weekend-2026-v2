from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.layout import (
    render_chip_row,
    render_metric_card,
    render_momentum_strip,
    render_page_action,
    render_placeholder_panel,
    render_section_header,
    render_status_card,
)
from domain.formatting import format_points, format_score_value
from domain.scoring import compute_optional_awards
from domain.weekend_config import team_short_name


def _format_total_table(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for column in ("Gross Total", "Net Total", "Best Gross Total", "Best Net Total"):
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(format_score_value)
    return formatted


def _next_pending_hole(summary: pd.DataFrame, result_column: str = "hole_result") -> int | None:
    if result_column not in summary.columns:
        return None
    pending = summary[summary[result_column].eq("Pending")]
    if pending.empty:
        return None
    return int(pending.iloc[0]["hole"])


def _match_leader_text(balance: int, left_label: str, right_label: str) -> tuple[str, str]:
    if balance > 0:
        return f"{left_label} are {abs(balance)} up", "red"
    if balance < 0:
        return f"{right_label} are {abs(balance)} up", "blue"
    return "Match all square", "neutral"


def _render_live_answer(result: dict[str, Any]) -> None:
    st.markdown("#### Live Answer")
    red_label = team_short_name("red")
    blue_label = team_short_name("blue")

    if result["format_name"] == "Singles":
        matches = result.get("matches", [])
        if not matches:
            return
        columns = st.columns(len(matches))
        for column, match in zip(columns, matches):
            next_hole = _next_pending_hole(match["summary_df"])
            status, tone = _match_leader_text(match["current_balance"], match["players"][0], match["players"][1])
            support = "Result complete" if match["is_complete"] else f"Hole {next_hole} is next" if next_hole else "Awaiting next saved hole"
            with column:
                render_status_card(match["label"], status, support, tone=tone)
        return

    if result["format_name"] == "Stroke Play":
        stroke_play = result.get("stroke_play", {})
        red_total = int(stroke_play.get("red_total", 0))
        blue_total = int(stroke_play.get("blue_total", 0))
        next_hole = _next_pending_hole(result["summary_df"])
        if red_total < blue_total:
            status, tone = f"{red_label} lead by {blue_total - red_total} net shots", "red"
        elif blue_total < red_total:
            status, tone = f"{blue_label} lead by {red_total - blue_total} net shots", "blue"
        else:
            status, tone = "Round all square on net better ball", "neutral"
        support = "Round complete" if result.get("is_complete") else f"Hole {next_hole} is the next counting swing" if next_hole else "Awaiting next saved hole"
        render_status_card("Stroke Play", status, support, tone=tone)
        return

    if result["format_name"] == "Skins":
        skins = result.get("skins", {})
        red_skins = int(skins.get("red_skins", 0))
        blue_skins = int(skins.get("blue_skins", 0))
        carryover = int(skins.get("carryover_skins", 1))
        next_hole = _next_pending_hole(result["summary_df"])
        if red_skins > blue_skins:
            status, tone = f"{red_label} lead by {red_skins - blue_skins} skins", "red"
        elif blue_skins > red_skins:
            status, tone = f"{blue_label} lead by {blue_skins - red_skins} skins", "blue"
        else:
            status, tone = "Skins all square", "neutral"
        if result.get("is_complete"):
            support = "Round complete"
        elif next_hole:
            support = f"Hole {next_hole} is next for {carryover} skin{'s' if carryover != 1 else ''}"
        else:
            support = "Awaiting next saved hole"
        render_status_card("Skins", status, support, tone=tone)
        return

    match = result.get("match")
    if not match:
        return
    left_label, right_label = match["label"].split(" vs ")
    next_hole = _next_pending_hole(match["summary_df"])
    status, tone = _match_leader_text(match["current_balance"], left_label, right_label)
    support = "Result complete" if match["is_complete"] else f"Hole {next_hole} is next" if next_hole else "Awaiting next saved hole"
    render_status_card("4-Ball", status, support, tone=tone)


def _render_points_cards(result: dict[str, Any]) -> None:
    awarded = result.get("awarded_points", {"red": 0.0, "blue": 0.0})
    projected = result.get("projected_points", {"red": 0.0, "blue": 0.0})
    red_label = team_short_name("red")
    blue_label = team_short_name("blue")
    columns = st.columns(4)
    with columns[0]:
        render_metric_card(f"{red_label} Awarded", format_points(float(awarded["red"])), "banked", tone="red")
    with columns[1]:
        render_metric_card(f"{blue_label} Awarded", format_points(float(awarded["blue"])), "banked", tone="blue")
    with columns[2]:
        render_metric_card(f"{red_label} Live", format_points(float(projected["red"])), "if it ended now", tone="red")
    with columns[3]:
        render_metric_card(f"{blue_label} Live", format_points(float(projected["blue"])), "if it ended now", tone="blue")


def render_match_centre_empty_state(
    selected_fixture: dict[str, Any],
    format_name: str,
    tee_label: str,
    round_focus: dict[str, Any],
) -> None:
    render_status_card(
        "Match Centre",
        "Live match view appears after hole 1 is saved",
        "Start scoring when you are ready. Match status and points swing update from the first saved hole.",
        tone="neutral",
    )
    render_chip_row([selected_fixture["title"], format_name, f"{tee_label} tees"], tone="accent")
    action_columns = st.columns(2)
    with action_columns[0]:
        render_page_action("pages/2_Live_Scoring.py", round_focus["primary_label"], key=f"match-empty-primary::{selected_fixture['id']}", primary=True)
    with action_columns[1]:
        render_page_action("pages/4_Course_Guide.py", "Open course guide", key=f"match-empty-secondary::{selected_fixture['id']}")
    render_placeholder_panel(
        "No live hole saved yet",
        "Save the opening hole in Live Scoring to bring the live match answer, momentum, and weekend points view online here.",
    )


def render_leaderboard(result: dict[str, Any], show_gross_secondary: bool, show_header: bool = True) -> None:
    red_label = team_short_name("red")
    blue_label = team_short_name("blue")
    if show_header:
        render_section_header(
            "Match Centre",
            "Round status, momentum, hole-by-hole swings, and weekend points impact for the selected round.",
        )

    summary = result.get("summary_df")
    if not isinstance(summary, pd.DataFrame) or summary.empty:
        st.info("Enter live scores to populate the match centre.")
        return

    _render_live_answer(result)
    _render_points_cards(result)

    if result["format_name"] == "Singles":
        player_index_lookup = {
            row["Player"]: int(row["Player Index"])
            for _, row in result["player_handicaps"].iterrows()
        }
        for match in result.get("matches", []):
            st.markdown(f"### {match['label']}")
            card_columns = st.columns(3)
            with card_columns[0]:
                render_status_card("Match Status", match["current_status"], f"{match['holes_played']} holes played")
            with card_columns[1]:
                render_metric_card("Last Hole", match["last_hole"]["result"] if match["last_hole"] else "Pending", f"Hole {match['last_hole']['hole']}" if match["last_hole"] else None)
            with card_columns[2]:
                render_metric_card("Handicap Base", match["relative_to"] or "—", "playing off")
            render_momentum_strip(match["momentum"], match["players"][0], match["players"][1])
            split_columns = st.columns(2)
            with split_columns[0]:
                render_metric_card("Front 9", f"{match['splits']['front'][match['players'][0]]}-{match['splits']['front'][match['players'][1]]}", f"Halved {match['splits']['front']['Halved']}")
            with split_columns[1]:
                render_metric_card("Back 9", f"{match['splits']['back'][match['players'][0]]}-{match['splits']['back'][match['players'][1]]}", f"Halved {match['splits']['back']['Halved']}")
            detail = match["summary_df"].rename(
                columns={
                    match["players"][0]: f"{match['players'][0]} Shots",
                    match["players"][1]: f"{match['players'][1]} Shots",
                    "left_net": f"{match['players'][0]} Net",
                    "right_net": f"{match['players'][1]} Net",
                    "hole_result": "Hole Result",
                    "status_text": "Match Status",
                }
            )
            detail = detail.rename(
                columns={
                    f"player_{player_index_lookup[match['players'][0]] + 1}": f"{match['players'][0]} Gross",
                    f"player_{player_index_lookup[match['players'][1]] + 1}": f"{match['players'][1]} Gross",
                }
            )
            with st.expander(f"{match['label']} hole-by-hole", expanded=False):
                st.dataframe(
                    detail[
                        [
                            "hole",
                            "par",
                            "si",
                            f"{match['players'][0]} Gross",
                            f"{match['players'][0]} Shots",
                            f"{match['players'][0]} Net",
                            f"{match['players'][1]} Gross",
                            f"{match['players'][1]} Shots",
                            f"{match['players'][1]} Net",
                            "Hole Result",
                            "Match Status",
                        ]
                    ].rename(columns={"hole": "Hole", "par": "Par", "si": "SI"}),
                    width="stretch",
                    hide_index=True,
                )

        if isinstance(result.get("player_totals"), pd.DataFrame) and not result["player_totals"].empty:
            st.markdown("#### Player Totals")
            st.dataframe(_format_total_table(result["player_totals"]), width="stretch", hide_index=True)

        if isinstance(result.get("team_totals"), pd.DataFrame) and not result["team_totals"].empty:
            st.markdown("#### Team Totals")
            st.dataframe(_format_total_table(result["team_totals"]), width="stretch", hide_index=True)
    elif result["format_name"] == "Stroke Play":
        stroke_play = result.get("stroke_play", {})
        headline_columns = st.columns(3)
        with headline_columns[0]:
            render_status_card("Stroke Play", stroke_play.get("current_status", "Awaiting scores"), f"{stroke_play.get('holes_played', 0)} holes played")
        with headline_columns[1]:
            render_metric_card(f"{red_label} Total", stroke_play.get("red_total", 0), "best net total", tone="red")
        with headline_columns[2]:
            render_metric_card(f"{blue_label} Total", stroke_play.get("blue_total", 0), "best net total", tone="blue")

        if "player_totals" in result and isinstance(result["player_totals"], pd.DataFrame) and not result["player_totals"].empty:
            st.markdown("#### Player Totals")
            st.dataframe(_format_total_table(result["player_totals"]), width="stretch", hide_index=True)

        if "team_totals" in result and isinstance(result["team_totals"], pd.DataFrame) and not result["team_totals"].empty:
            st.markdown("#### Team Totals")
            st.dataframe(_format_total_table(result["team_totals"]), width="stretch", hide_index=True)

        with st.expander("Stroke play hole-by-hole", expanded=False):
            score_columns = [
                "hole",
                "par",
                "si",
                "team_a_best_net",
                "team_b_best_net",
                "red_running_total",
                "blue_running_total",
                "team_a_contributor",
                "team_b_contributor",
                "hole_result",
            ]
            st.dataframe(
                result["summary_df"][score_columns].rename(
                    columns={
                        "hole": "Hole",
                        "par": "Par",
                        "si": "SI",
                        "team_a_best_net": f"{red_label} Best Net",
                        "team_b_best_net": f"{blue_label} Best Net",
                        "red_running_total": f"{red_label} Running Total",
                        "blue_running_total": f"{blue_label} Running Total",
                        "team_a_contributor": f"{red_label} Counter",
                        "team_b_contributor": f"{blue_label} Counter",
                        "hole_result": "Hole Result",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
    elif result["format_name"] == "Skins":
        skins = result.get("skins", {})
        headline_columns = st.columns(4)
        with headline_columns[0]:
            render_status_card("Skins", skins.get("current_status", "Awaiting scores"), f"{skins.get('holes_played', 0)} holes played")
        with headline_columns[1]:
            render_metric_card(f"{red_label} Skins", skins.get("red_skins", 0), "won", tone="red")
        with headline_columns[2]:
            render_metric_card(f"{blue_label} Skins", skins.get("blue_skins", 0), "won", tone="blue")
        with headline_columns[3]:
            render_metric_card("Current Pot", skins.get("carryover_skins", 1), "next hole")

        if "player_totals" in result and isinstance(result["player_totals"], pd.DataFrame) and not result["player_totals"].empty:
            st.markdown("#### Player Totals")
            st.dataframe(_format_total_table(result["player_totals"]), width="stretch", hide_index=True)

        if "team_totals" in result and isinstance(result["team_totals"], pd.DataFrame) and not result["team_totals"].empty:
            st.markdown("#### Team Totals")
            st.dataframe(_format_total_table(result["team_totals"]), width="stretch", hide_index=True)

        with st.expander("Skins hole-by-hole", expanded=False):
            score_columns = [
                "hole",
                "par",
                "si",
                "team_a_best_net",
                "team_b_best_net",
                "skins_pot",
                "red_skins_awarded",
                "blue_skins_awarded",
                "red_running_skins",
                "blue_running_skins",
                "team_a_contributor",
                "team_b_contributor",
                "hole_result",
            ]
            st.dataframe(
                result["summary_df"][score_columns].rename(
                    columns={
                        "hole": "Hole",
                        "par": "Par",
                        "si": "SI",
                        "team_a_best_net": f"{red_label} Best Net",
                        "team_b_best_net": f"{blue_label} Best Net",
                        "skins_pot": "Skins Pot",
                        "red_skins_awarded": f"{red_label} Skins Awarded",
                        "blue_skins_awarded": f"{blue_label} Skins Awarded",
                        "red_running_skins": f"{red_label} Running Skins",
                        "blue_running_skins": f"{blue_label} Running Skins",
                        "team_a_contributor": f"{red_label} Counter",
                        "team_b_contributor": f"{blue_label} Counter",
                        "hole_result": "Hole Result",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
    else:
        match = result.get("match")
        if match:
            headline_columns = st.columns(3)
            with headline_columns[0]:
                render_status_card("Current Match", match["current_status"], f"{match['holes_played']} holes played")
            with headline_columns[1]:
                render_metric_card("Last Hole", match["last_hole"]["result"] if match["last_hole"] else "Pending", f"Hole {match['last_hole']['hole']}" if match["last_hole"] else None)
            with headline_columns[2]:
                render_metric_card("Handicap Base", match["relative_to"] or "Gross", "playing off")

            render_momentum_strip(match["momentum"], match["label"].split(" vs ")[0], match["label"].split(" vs ")[1])
            split_columns = st.columns(2)
            left_label, right_label = match["label"].split(" vs ")
            with split_columns[0]:
                render_metric_card("Front 9", f"{match['splits']['front'][left_label]}-{match['splits']['front'][right_label]}", f"Halved {match['splits']['front']['Halved']}")
            with split_columns[1]:
                render_metric_card("Back 9", f"{match['splits']['back'][left_label]}-{match['splits']['back'][right_label]}", f"Halved {match['splits']['back']['Halved']}")

        if "player_totals" in result and isinstance(result["player_totals"], pd.DataFrame) and not result["player_totals"].empty:
            st.markdown("#### Player Totals")
            st.dataframe(_format_total_table(result["player_totals"]), width="stretch", hide_index=True)

        if "team_totals" in result and isinstance(result["team_totals"], pd.DataFrame) and not result["team_totals"].empty:
            st.markdown("#### Team Totals")
            st.dataframe(_format_total_table(result["team_totals"]), width="stretch", hide_index=True)

        st.caption("Hole outcomes are decided by best net ball. Gross best ball can still be reviewed below.")
        detail = result["summary_df"].copy()
        columns = [
            "hole",
            "par",
            "si",
            "hole_result",
            "match_status",
            "team_a_best_net",
            "team_b_best_net",
            "team_a_contributor",
            "team_b_contributor",
        ]
        if show_gross_secondary:
            columns.extend(["team_a_best_gross", "team_b_best_gross"])
        with st.expander("4-Ball hole-by-hole", expanded=False):
            st.dataframe(
                detail[columns].rename(
                    columns={
                        "hole": "Hole",
                        "par": "Par",
                        "si": "SI",
                        "hole_result": "Hole Result",
                        "match_status": "Match Status",
                        "team_a_best_net": f"{red_label} Best Net",
                        "team_b_best_net": f"{blue_label} Best Net",
                        "team_a_contributor": f"{red_label} Counter",
                        "team_b_contributor": f"{blue_label} Counter",
                        "team_a_best_gross": f"{red_label} Best Gross",
                        "team_b_best_gross": f"{blue_label} Best Gross",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

    awards = compute_optional_awards(result)
    if awards:
        st.markdown("#### End-Of-Round Extras")
        award_columns = st.columns(len(awards))
        for column, award in zip(award_columns, awards):
            with column:
                render_metric_card(award["title"], award["value"], None)

    st.download_button(
        "Download round summary (CSV)",
        data=result["export_bytes"],
        file_name=f"{result['format_name'].lower().replace(' ', '-')}-summary.csv",
        mime="text/csv",
    )
