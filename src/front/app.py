from __future__ import annotations

from pathlib import Path
import requests
import pandas as pd

import streamlit as st

P_FRONT = Path(__file__).parent
P_TEST = P_FRONT / "test"


# streamlit run app.py
class MainApp:
  def __init__(self):
    st.set_page_config(page_title="설비 예지 보전 대시보드", layout="wide")
    st.title("설비 예지 보전 대시보드")

    if "simulate" not in st.session_state:
      st.session_state.simulate = None

    if st.button("simulate"):
      try:
        response = requests.get("http://127.0.0.1:8000/simulate")
        response.raise_for_status()

        st.session_state.simulate = pd.DataFrame(response.json())
      except requests.RequestException as e:
        st.error(f"서버 요청 실패: {e}")

    if st.session_state.simulate is not None:
      st.dataframe(st.session_state.simulate, use_container_width=True)

    st.write("test")


def handle_button():
  st.toast("Component 버튼 클릭")


def test():
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


if __name__ == "__main__":
  app = MainApp()
