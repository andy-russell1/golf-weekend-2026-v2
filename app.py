from __future__ import annotations

import streamlit as st

from domain.weekend_config import TOURNAMENT_NAME


def main() -> None:
    st.set_page_config(page_title=TOURNAMENT_NAME, layout="wide")

    navigation = st.navigation(
        [
            st.Page("pages/1_Weekend_Hub.py", title="Weekend Hub", default=True),
            st.Page("pages/2_Live_Scoring.py", title="Live Scoring"),
            st.Page("pages/3_Match_Centre.py", title="Match Centre"),
            st.Page("pages/4_Course_Guide.py", title="Course Guide"),
            st.Page("pages/5_Setup_Admin.py", title="Setup Admin"),
        ],
        position="sidebar",
    )
    navigation.run()


if __name__ == "__main__":
    main()
