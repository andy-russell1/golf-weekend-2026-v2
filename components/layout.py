from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from domain.weekend_config import team_short_name


def load_css(css_path: Path) -> None:
    if not css_path.exists():
        return
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
    components.html(
        """
        <script>
        const parentDoc = window.parent.document;
        const parentWin = window.parent;

        function parseColorValues(rawColor) {
          return rawColor && rawColor.match(/[\\d.]+/g);
        }

        function readThemeProbeColor() {
          const probe = Array.from(parentDoc.body.querySelectorAll("div")).find((node) => {
            const style = parentWin.getComputedStyle(node);
            return style.position === "fixed" && style.pointerEvents === "none" && Number(style.opacity) === 0;
          });

          if (probe) {
            return parentWin.getComputedStyle(probe).color;
          }

          const appView = parentDoc.querySelector('[data-testid="stAppViewContainer"]');
          if (appView) {
            return parentWin.getComputedStyle(appView).backgroundColor;
          }

          return parentWin.getComputedStyle(parentDoc.body).backgroundColor;
        }

        function setAppTheme() {
          const probeColor = readThemeProbeColor();
          const values = parseColorValues(probeColor);
          if (!values || values.length < 3) {
            const systemPrefersDark = parentWin.matchMedia("(prefers-color-scheme: dark)").matches;
            parentDoc.documentElement.setAttribute("data-rki-theme", systemPrefersDark ? "dark" : "light");
            return;
          }

          const [r, g, b] = values.slice(0, 3).map(Number);
          const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
          parentDoc.documentElement.setAttribute("data-rki-theme", luminance < 0.5 ? "dark" : "light");
        }

        setAppTheme();
        const observer = new MutationObserver(() => parentWin.requestAnimationFrame(setAppTheme));
        observer.observe(parentDoc.documentElement, { attributes: true, childList: true, subtree: true });
        parentWin.addEventListener("storage", () => parentWin.requestAnimationFrame(setAppTheme));
        parentWin.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => parentWin.requestAnimationFrame(setAppTheme));
        </script>
        """,
        height=0,
        width=0,
    )


def render_hero(title: str, subtitle: str, meta: str) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-kicker">Golf Weekend 2026</div>
            <div class="hero-title">{title}</div>
            <div class="hero-subtitle">{subtitle}</div>
            <div class="hero-meta">{meta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: str | None = None) -> None:
    subtitle_markup = f'<div class="section-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="section-heading">
            <div class="section-title">{title}</div>
            {subtitle_markup}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: Any, supporting: str | None = None, tone: str = "neutral") -> None:
    supporting_markup = f'<div class="metric-support">{supporting}</div>' if supporting else ""
    st.markdown(
        f"""
        <div class="metric-card metric-card-{tone}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {supporting_markup}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_card(title: str, status: str, supporting: str | None = None, tone: str = "neutral") -> None:
    supporting_markup = f'<div class="status-support">{supporting}</div>' if supporting else ""
    st.markdown(
        f"""
        <div class="status-card status-card-{tone}">
            <div class="status-title">{title}</div>
            <div class="status-value">{status}</div>
            {supporting_markup}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_fixture_card(
    title: str,
    format_name: str,
    schedule: str,
    status: str,
    red_points: str,
    blue_points: str,
) -> None:
    st.markdown(
        f"""
        <div class="fixture-card">
            <div class="fixture-header">
                <div class="fixture-title">{title}</div>
                <div class="fixture-format">{format_name}</div>
            </div>
            <div class="fixture-schedule">{schedule}</div>
            <div class="fixture-status">{status}</div>
            <div class="fixture-points">
                <span class="fixture-point fixture-point-red">{team_short_name("red")} {red_points}</span>
                <span class="fixture-point fixture-point-blue">{team_short_name("blue")} {blue_points}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_badge(label: str, tone: str = "muted") -> None:
    st.markdown(f'<span class="badge badge-{tone}">{label}</span>', unsafe_allow_html=True)


def render_placeholder_panel(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="placeholder-panel">
            <div class="placeholder-title">{title}</div>
            <div class="placeholder-body">{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chip_row(items: list[str], tone: str = "muted") -> None:
    chips = "".join(f'<span class="info-chip info-chip-{tone}">{item}</span>' for item in items if item)
    if chips:
        st.markdown(f'<div class="chip-row">{chips}</div>', unsafe_allow_html=True)


def render_momentum_strip(items: list[str], positive_label: str, negative_label: str) -> None:
    tokens: list[str] = []
    for item in items:
        if item == positive_label:
            token_class = "momentum-red"
            text = "R"
        elif item == negative_label:
            token_class = "momentum-blue"
            text = "B"
        elif item == "Halved":
            token_class = "momentum-half"
            text = "H"
        else:
            token_class = "momentum-pending"
            text = "·"
        tokens.append(f'<span class="momentum-pill {token_class}">{text}</span>')
    st.markdown(f'<div class="momentum-strip">{"".join(tokens)}</div>', unsafe_allow_html=True)


def render_connection_panel(status: dict[str, Any], compact: bool = False) -> None:
    state = str(status.get("state", "disconnected"))
    title = "Sheets"
    message = str(status.get("message", "Not connected"))
    workbook = str(status.get("workbook_title") or status.get("workbook_name") or "")
    auth_mode = str(status.get("auth_mode_label", ""))
    principal = str(status.get("principal") or status.get("service_account_email") or "")
    checked_at = str(status.get("last_checked_at", ""))
    tone = "green" if state == "connected" else "gold" if state == "auth_required" else "red"
    if compact:
        chips = [message]
        if auth_mode:
            chips.append(auth_mode)
        if workbook:
            chips.append(workbook)
        render_chip_row(chips, tone="accent" if state == "connected" else "muted")
        return
    render_status_card(
        title,
        message,
        " • ".join(item for item in (auth_mode, principal, workbook, f"Checked {checked_at}" if checked_at else "") if item),
        tone=tone,
    )


def render_page_action(destination: str, label: str, key: str, primary: bool = False) -> None:
    button_type = "primary" if primary else "secondary"
    if st.button(label, key=key, width="stretch", type=button_type):
        st.switch_page(destination)
