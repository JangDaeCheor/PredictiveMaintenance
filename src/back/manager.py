from fastapi import FastAPI, APIRouter, Body, HTTPException, Response
from fastapi.responses import PlainTextResponse
import back.message as ms
from back.simulator import Simulator
from back.worker import Worker


class MainManager(Worker):
  def __init__(self):
    super().__init__(name=ms.WorkerName.MainManager)
    self._running_cmd = []
    self._result = []  # emit_message queue는 쓰기 힘드네.

    self.app = FastAPI()
    self.router = APIRouter()

    self.router.add_api_route(
      "/simulator/truth",
      self.request_simulator_truth,
      methods=["POST"],
    )
    self.router.add_api_route(
      "/simulator/status",
      self.response_simulator_status,
      methods=["GET"],
    )
    self.router.add_api_route(
      "/simulator/truth",
      self.get_simulator_truth,
      methods=["GET"],
    )

    self.simulator = Simulator(42)
    self.simulator.start()

    self.app.include_router(self.router)

  # def simulate(self):
  #   return [
  #     {"온도": 72.1, "진동": 3.2, "회전수": 1420},
  #     {"온도": 73.5, "진동": 3.5, "회전수": 1430},
  #     {"온도": 71.8, "진동": 3.1, "회전수": 1415},
  #   ]

  def get_running_cmd(self, event):
    for status in self._running_cmd:
      if event in status:
        return status
    return None

  def del_running_cmd(self, event):
    for status in self._running_cmd:
      if event in status:
        self._running_cmd.remove(status)
        return True
    return False

  def request_simulator_truth(self, params: dict = Body(...)):
    message = ms.Message(ms.MessageType.EVENT, ms.Event(ms.Event.SimulateTruth, params))
    self._running_cmd.append({ms.Event.SimulateTruth: "running"})
    self.simulator.receive_message(message)

  # 결과 응답시 결과 데이터를 발송하고 삭제하므로 front에서 결과 응답을 놓칠 시 이후에는 409error 발생
  def get_simulator_truth(self):
    for result in self._result:
      if ms.Event.SimulateTruth in result:
        self._result.remove(result)
        data = result[ms.Event.SimulateTruth]
        return Response(
          content=data.to_json(orient="records", date_format="iso"),
          media_type="application/json",
        )
    raise HTTPException(status_code=409, detail="시뮬레이션 결과가 없음")

  # 상태 조회시 완료 상태면 삭제하므로 front에서 완료 응답을 놓칠 시 이후에는 "none"만 받음
  def response_simulator_status(self):
    cmd = self.get_running_cmd(ms.Event.SimulateTruth)

    if cmd is not None:
      status = cmd[ms.Event.SimulateTruth]
      if status == "completed":
        self.del_running_cmd(ms.Event.SimulateTruth)
      return PlainTextResponse(status)
    return PlainTextResponse("none")

  def _handle_message(self):
    msg_simulator = self.simulator.take_message()

    if msg_simulator is not None:
      if msg_simulator.type == ms.MessageType.FEEDBACK:
        status = self.get_running_cmd(ms.Event.SimulateTruth)
        if status is not None:
          self._result.append({ms.Event.SimulateTruth: msg_simulator.content})
          status[ms.Event.SimulateTruth] = "completed"


manager = MainManager()
app = manager.app
manager.start()
