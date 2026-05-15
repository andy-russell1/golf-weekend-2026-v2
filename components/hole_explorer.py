from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.layout import render_chip_row, render_metric_card, render_placeholder_panel, render_section_header
from support.data_loader import get_hole_image, get_hole_record, load_course_data
from domain.formatting import difficulty_label, format_hole_name, format_relative_to
from domain.scoring import get_hole_shots_for_display


def render_hole_explorer(
    course: str,
    selected_tee: str,
    shot_views: list[dict[str, Any]],
    current_active_hole: int,
) -> dict[str, Any]:
    course_df = load_course_data(course)
    if course_df.empty:
        st.warning("No hole data is available for this course.")
        return {"selected_hole": current_active_hole, "open_live_scoring": False}

    render_section_header(
        "Hole Explorer",
        "Hole notes, images, yardages, and current handicap shots for the selected round setup.",
    )

    hole_options = [int(hole) for hole in course_df["hole"].dropna().tolist()]
    default_hole = current_active_hole if current_active_hole in hole_options else hole_options[0]
    selected_hole = st.selectbox("Hole to review", options=hole_options, index=hole_options.index(default_hole))

    hole_record = get_hole_record(course, selected_hole)
    image_record = get_hole_image(course, selected_hole)

    hole_name = format_hole_name(hole_record.get("hole_name"), selected_hole)
    yardage_key = "yards_white" if selected_tee.lower() == "white" else "yards_yellow"
    alternate_key = "yards_yellow" if yardage_key == "yards_white" else "yards_white"
    selected_yardage = hole_record.get(yardage_key)
    alternate_yardage = hole_record.get(alternate_key)
    difficulty, _ = difficulty_label(hole_record.get("si"))

    st.markdown(f"### {hole_name}")
    render_chip_row([f"Par {hole_record.get('par', '—')}", f"SI {hole_record.get('si', '—')}", difficulty])
    open_live_scoring = st.button("Open This Hole In Live Scoring", width="stretch")

    metric_columns = st.columns(2)
    metric_values = [
        ("Selected Tee", selected_yardage if pd.notna(selected_yardage) else "\u2014", "yards"),
        ("Alternate Tee", alternate_yardage if pd.notna(alternate_yardage) else "\u2014", "yards"),
    ]
    for column, (label, value, supporting) in zip(metric_columns, metric_values):
        with column:
            render_metric_card(label, value, supporting)

    shot_display = get_hole_shots_for_display(shot_views, selected_hole)
    st.markdown("#### Shots Received On This Hole")
    if not shot_display:
        st.caption("Handicap shot guidance will appear here once tee ratings and players are loaded.")
    else:
        for group in shot_display:
            shot_text = [f"{label}: {shots}" for label, shots in group["shots"].items()]
            render_chip_row([group["label"], format_relative_to(group["relative_to"]), *shot_text])

    content_columns = st.columns([1.35, 1], gap="large")
    with content_columns[0]:
        if image_record["available"]:
            st.image(str(image_record["path"]), use_container_width=True)
            if image_record.get("caption"):
                st.caption(image_record["caption"])
        else:
            render_placeholder_panel("No official image available", image_record.get("message", "No official image available"))

    with content_columns[1]:
        st.markdown("#### Hole Tip")
        pro_tip = hole_record.get("pro_tip")
        if isinstance(pro_tip, str) and pro_tip.strip():
            st.write(pro_tip.strip())
        else:
            st.caption("No official tip available for this hole.")

        st.markdown("#### Notes")
        notes = hole_record.get("image_notes")
        if isinstance(notes, str) and notes.strip():
            st.write(notes.strip())
        else:
            st.caption("No extra notes logged for this hole.")

    return {"selected_hole": selected_hole, "open_live_scoring": open_live_scoring}
