from __future__ import annotations

from domain.scoring import compute_round_results
from domain.scorecard_export import build_premium_scorecard_pdf, build_scorecard_round_payload, premium_scorecard_filename
from domain.weekend_config import FIXTURES, default_handicap_indexes, default_player_ids, default_player_names
from support.data_loader import get_tee_rating, load_course_data
from support.session import blank_scores


def test_premium_scorecard_export_builds_pdf_bytes() -> None:
    fixture = FIXTURES[0]
    course_df = load_course_data(fixture["course"])
    holes = [int(hole) for hole in course_df["hole"].dropna().tolist()]
    scores = blank_scores(holes, "4-Ball")

    for index in range(4):
        scores[f"player_{index + 1}"] = course_df["par"].astype(int) + (index % 2)
    scores["status"] = "Complete"

    player_names = default_player_names()
    result = compute_round_results(
        course_df=course_df,
        format_name="4-Ball",
        score_df=scores,
        player_names=player_names,
        player_ids=default_player_ids(),
        handicap_indexes=default_handicap_indexes(),
        tee_rating=get_tee_rating(fixture["course"], fixture["default_tee"]),
        allowance_percent=100,
        scoring_mode="net",
        handicap_allocation="relative",
    )
    payload = build_scorecard_round_payload(
        fixture=fixture,
        round_runtime={
            "round_id": fixture["id"],
            "round_order": fixture["round_order"],
            "format_name": "4-Ball",
            "tee_label": fixture["default_tee"],
            "allowance_percent": 100,
        },
        round_state={
            "player_ids": default_player_ids(),
            "player_names": player_names,
            "handicap_indexes": default_handicap_indexes(),
            "scores": scores,
        },
        result=result,
    )

    pdf = build_premium_scorecard_pdf([payload])

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2_000
    assert premium_scorecard_filename([payload]) == "premium-scorecard-rolls_monmouth.pdf"
