from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

P_GUI = Path(__file__).parent
P_TEST = P_GUI / "test"


def handle_button():
  st.toast("Component 버튼 클릭")


def main():
  st.set_page_config(page_title="설비 예지 보전 대시보드", layout="wide")

  st.title("설비 예지 보전 대시보드")

  test_button = st.components.v2.component(
    name="test_button",
    html=(P_TEST / "component.html").read_text(encoding="utf-8"),
    js=(P_TEST / "component.js").read_text(encoding="utf-8"),
  )

  result = test_button(
    on_action_change=handle_button,
  )

  if result.action:
    st.write("test:", result.action)


main()
