from __future__ import annotations

import streamlit as st

from support.app_context import initialize_page


def main() -> None:
    if not initialize_page("Weekend Hub"):
        return

    st.switch_page("app.py")


if __name__ == "__main__":
    main()
