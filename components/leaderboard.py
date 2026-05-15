from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.layout import render_metric_card, render_momentum_strip, render_section_header, render_status_card
from domain.formatting import format_points, format_score_value
from domain.scoring import compute_optional_awards


def _format_total_table(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    for column in ("Gross Total", "Net Total", "Best Gross Total", "Best Net Total"):
        if column in formatted.columns:
            formatted[column] = formatted[column].apply(format_score_value)
    return formatted


def _render_points_cards(result: dict[str, Any]) -> None:
    awarded = result.get("awarded_points", {"red": 0.0, "blue": 0.0})
    projected = result.get("projected_points", {"red": 0.0, "blue": 0.0})
    columns = st.columns(4)
    with columns[0]:
        render_metric_card("Red Awarded", format_points(float(awarded["red"])), "banked", tone="red")
    with columns[1]:
        render_metric_card("Blue Awarded", format_points(float(awarded["blue"])), "banked", tone="blue")
    with columns[2]:
        render_metric_card("Red Live", format_points(float(projected["red"])), "if it ended now", tone="red")
    with columns[3]:
        render_metric_card("Blue Live", format_points(float(projected["blue"])), "if it ended now", tone="blue")


def render_leaderboard(result: dict[str, Any], show_gross_secondary: bool, show_header: bool = True) -> None:
    if show_header:
        render_section_header(
            "Match Centre",
            "Round status, momentum, hole-by-hole swings, and Ryder Cup points impact for the selected round.",
        )

    summary = result.get("summary_df")
    if not isinstance(summary, pd.DataFrame) or summary.empty:
        st.info("Enter live scores to populate the match centre.")
        return

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
                    use_container_width=True,
                    hide_index=True,
                )

        if isinstance(result.get("player_totals"), pd.DataFrame) and not result["player_totals"].empty:
            st.markdown("#### Player Totals")
            st.dataframe(_format_total_table(result["player_totals"]), use_container_width=True, hide_index=True)

        if isinstance(result.get("team_totals"), pd.DataFrame) and not result["team_totals"].empty:
            st.markdown("#### Team Totals")
            st.dataframe(_format_total_table(result["team_totals"]), use_container_width=True, hide_index=True)
    elif result["format_name"] == "Stroke Play":
        stroke_play = result.get("stroke_play", {})
        headline_columns = st.columns(3)
        with headline_columns[0]:
            render_status_card("Stroke Play", stroke_play.get("current_status", "Awaiting scores"), f"{stroke_play.get('holes_played', 0)} holes played")
        with headline_columns[1]:
            render_metric_card("Red Total", stroke_play.get("red_total", 0), "best net total", tone="red")
        with headline_columns[2]:
            render_metric_card("Blue Total", stroke_play.get("blue_total", 0), "best net total", tone="blue")

        if "player_totals" in result and isinstance(result["player_totals"], pd.DataFrame) and not result["player_totals"].empty:
            st.markdown("#### Player Totals")
            st.dataframe(_format_total_table(result["player_totals"]), use_container_width=True, hide_index=True)

        if "team_totals" in result and isinstance(result["team_totals"], pd.DataFrame) and not result["team_totals"].empty:
            st.markdown("#### Team Totals")
            st.dataframe(_format_total_table(result["team_totals"]), use_container_width=True, hide_index=True)

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
                        "team_a_best_net": "Red Best Net",
                        "team_b_best_net": "Blue Best Net",
                        "red_running_total": "Red Running Total",
                        "blue_running_total": "Blue Running Total",
                        "team_a_contributor": "Red Counter",
                        "team_b_contributor": "Blue Counter",
                        "hole_result": "Hole Result",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
    elif result["format_name"] == "Skins":
        skins = result.get("skins", {})
        headline_columns = st.columns(4)
        with headline_columns[0]:
            render_status_card("Skins", skins.get("current_status", "Awaiting scores"), f"{skins.get('holes_played', 0)} holes played")
        with headline_columns[1]:
            render_metric_card("Red Skins", skins.get("red_skins", 0), "won", tone="red")
        with headline_columns[2]:
            render_metric_card("Blue Skins", skins.get("blue_skins", 0), "won", tone="blue")
        with headline_columns[3]:
            render_metric_card("Current Pot", skins.get("carryover_skins", 1), "next hole")

        if "player_totals" in result and isinstance(result["player_totals"], pd.DataFrame) and not result["player_totals"].empty:
            st.markdown("#### Player Totals")
            st.dataframe(_format_total_table(result["player_totals"]), use_container_width=True, hide_index=True)

        if "team_totals" in result and isinstance(result["team_totals"], pd.DataFrame) and not result["team_totals"].empty:
            st.markdown("#### Team Totals")
            st.dataframe(_format_total_table(result["team_totals"]), use_container_width=True, hide_index=True)

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
                        "team_a_best_net": "Red Best Net",
                        "team_b_best_net": "Blue Best Net",
                        "skins_pot": "Skins Pot",
                        "red_skins_awarded": "Red Skins Awarded",
                        "blue_skins_awarded": "Blue Skins Awarded",
                        "red_running_skins": "Red Running Skins",
                        "blue_running_skins": "Blue Running Skins",
                        "team_a_contributor": "Red Counter",
                        "team_b_contributor": "Blue Counter",
                        "hole_result": "Hole Result",
                    }
                ),
                use_container_width=True,
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
            st.dataframe(_format_total_table(result["player_totals"]), use_container_width=True, hide_index=True)

        if "team_totals" in result and isinstance(result["team_totals"], pd.DataFrame) and not result["team_totals"].empty:
            st.markdown("#### Team Totals")
            st.dataframe(_format_total_table(result["team_totals"]), use_container_width=True, hide_index=True)

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
                        "team_a_best_net": "Red Best Net",
                        "team_b_best_net": "Blue Best Net",
                        "team_a_contributor": "Red Counter",
                        "team_b_contributor": "Blue Counter",
                        "team_a_best_gross": "Red Best Gross",
                        "team_b_best_gross": "Blue Best Gross",
                    }
                ),
                use_container_width=True,
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
