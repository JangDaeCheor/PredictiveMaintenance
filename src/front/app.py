from pathlib import Path
import requests
import pandas as pd

import streamlit as st

P_FRONT = Path(__file__).parent
P_TEST = P_FRONT / "test"

API_URL = "http://127.0.0.1:8000"


# streamlit run app.py
class MainApp:
  def __init__(self):
    st.set_page_config(page_title="설비 예지 보전 대시보드", layout="wide")
    st.title("설비 예지 보전 대시보드")

    self.init_state()

    st.write("test")

  @st.fragment(run_every="2s")
  def run(self):
    self.polling()

    self.simulator_form()

  def simulator_form(self):
    start_date = st.date_input("시작 날짜")
    n_samples = st.number_input("생성 개수", min_value=1, value=100)

    if st.button("simulate truth", disabled=st.session_state.simulator["polling"]):
      self.poll_truth(start_date.isoformat(), int(n_samples))

    data = st.session_state.simulator["truth"]
    if data is not None:
      st.success("시뮬레이션 완료")
      st.dataframe(data, use_container_width=True)

  def init_state(self):
    if "simulator" not in st.session_state:
      st.session_state.simulator = {"truth": None, "polling": False}

  def poll_truth(self, start: str, n_samples: int):
    if st.session_state.simulator["polling"]:
      return

    try:
      response = requests.post(
        f"{API_URL}/simulator/truth",
        json={"start": start, "n_samples": n_samples},
        timeout=(3, 10),
      )
      response.raise_for_status()

      st.session_state.simulator["truth"] = None
      st.session_state.simulator["polling"] = True

      st.success("시뮬레이션 작업을 시작했습니다.")
    except requests.RequestException as e:
      st.error(f"시뮬레이션 시작 실패: {e}")

  def load_data(self, data):
    try:
      # timeout=(연결 제한 시간, 응답 읽기 제한 시간)
      response = requests.get(f"{API_URL}/{data}", timeout=(3, 30))
      response.raise_for_status()

      return response.json()
    except requests.RequestException as e:
      st.error(f"데이터 조회 실패: {e}")

  def polling(self):
    if st.session_state.simulator["polling"]:
      status = self.get_status("simulator")

      if status is None:
        st.session_state.simulator["polling"] = False
        st.session_state.simulator["truth"] = None
      elif status == "completed":
        st.session_state.simulator["truth"] = self.load_data("simulator/truth")
        st.session_state.simulator["polling"] = False

  def get_status(self, data):
    try:
      # timeout=(연결 제한 시간, 응답 읽기 제한 시간)
      response = requests.get(f"{API_URL}/{data}/status", timeout=(3, 5))
      response.raise_for_status()
      return response.text
    except requests.RequestException as e:
      st.error(f"상태 조회 실패: {e}")
      return


# def handle_button():
#   st.toast("Component 버튼 클릭")


# def test():
#   st.set_page_config(page_title="설비 예지 보전 대시보드", layout="wide")

#   st.title("설비 예지 보전 대시보드")

#   test_button = st.components.v2.component(
#     name="test_button",
#     html=(P_TEST / "component.html").read_text(encoding="utf-8"),
#     js=(P_TEST / "component.js").read_text(encoding="utf-8"),
#   )

#   result = test_button(
#     on_action_change=handle_button,
#   )

#   if result.action:
#     st.write("test:", result.action)


if __name__ == "__main__":
  app = MainApp()
  app.run()
