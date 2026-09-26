from fastapi import FastAPI, APIRouter, Body, HTTPException, Response
from fastapi.responses import PlainTextResponse
import back.message as ms
from back.simulator import Simulator
from back.db import DB
from back.worker import Worker


class MainManager(Worker):
  def __init__(self):
    super().__init__(name=ms.WorkerName.MainManager)
    self._running_cmd = []
    self._running_work = []
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

    self.db = DB()
    self.db.start()

    self.app.include_router(self.router)

  # def simulate(self):
  #   return [
  #     {"온도": 72.1, "진동": 3.2, "회전수": 1420},
  #     {"온도": 73.5, "진동": 3.5, "회전수": 1430},
  #     {"온도": 71.8, "진동": 3.1, "회전수": 1415},
  #   ]

  def get_running_work(self, id):
    for work in self._running_work:
      if work.id == id:
        return work

  def get_running_event(self, event):
    works = []
    for work in self._running_work:
      if isinstance(work.content, ms.Event):
        if work.content.event == event:
          works.append(work)
    return works

  def del_work(self, work):
    if work in self._running_work:
      self._running_work.remove(work)
      return True
    return False

  def del_running_cmd(self, command):
    for cmd in self._running_cmd:
      if cmd["command"] == command:
        self._running_cmd.remove(cmd)
        return True
    return False

  def request_simulator_truth(self, params: dict = Body(...)):
    message = ms.Message(
      params["id"],
      ms.MessageType.EVENT,
      ms.Status.Running,
      ms.Event(ms.Event.SimulateTruth, params),
    )
    self._running_work.append(message)
    self.simulator.receive_message(message)

  # 결과 응답시 결과 데이터를 발송하고 삭제하므로 front에서 결과 응답을 놓칠 시 이후에는 409error 발생
  def get_simulator_truth(self, params: dict = Body(...)):
    work = self.get_running_work(params["id"])

    if work is None:
      raise HTTPException(status_code=409, detail="시뮬레이션 결과가 없음")
    elif work.status == ms.Status.Running:
      raise HTTPException(status_code=409, detail="시뮬레이션 진행 중")
    elif work.status == ms.Status.Failed:
      self._running_work.remove(work)
      raise HTTPException(status_code=409, detail="시뮬레이션 실패")
    elif work.status == ms.Status.Completed:
      response = Response(
        content=work.content.content.to_json(orient="records", date_format="iso"),
        media_type="application/json",
      )
      self._running_work.remove(work) # 전송 중 타임아웃이 발생하면 다시 결과를 받을 수 없음.
      return response

  # 상태 조회시 완료 상태면 삭제하므로 front에서 완료 응답을 놓칠 시 이후에는 "none"만 받음
  def response_simulator_status(self, params: dict = Body(...)):
    work = self.get_running_work(params["id"])

    if work is None:
      return {"status": ms.Status.Non.value, "error": None}
    elif work.status == ms.Status.Failed:
      return {"status": work.status.value, "error": work.content}
    else:
      return {"status": work.status.value, "error": None}

  def _handle_message(self):
    works = self.get_running_event(ms.Event.SimulateTruth)
    msg_simulator = self.simulator.take_message()

    if msg_simulator is not None and len(works) != 0:
      work = self.get_running_work(msg_simulator.id)

      if work is None:
        pass  # simulator에서 받아온 work가 MainManager에 저장되어 있지 않음..
      elif msg_simulator.type == ms.MessageType.FEEDBACK:
        msg_simulator.type = ms.MessageType.EVENT
        msg_simulator.content = ms.Event(ms.Event.DBInsert, msg_simulator.content)

        self.db.receive_message(msg_simulator)

        self._running_work.remove(work)
        self._running_work.append(msg_simulator)
      elif msg_simulator.type == ms.MessageType.ERROR:
        self._running_work.remove(work)
        work.status = ms.Status.Failed
        work.content = msg_simulator.content
        self._running_work.append(work)

    works = self.get_running_event(ms.Event.DBInsert)
    msg_db = self.db.take_message()

    if msg_db is not None and len(works) != 0:
      work = self.get_running_work(msg_db.id)

      if work is None:
        pass
      elif msg_db.type == ms.MessageType.FEEDBACK:
        self._running_work.remove(work)
        work.status = ms.Status.Completed
        self._running_work.append(work)
      elif msg_db.type == ms.MessageType.ERROR:
        self._running_work.remove(work)
        work.status = ms.Status.Failed
        work.content = msg_db.content
        self._running_work.append(work)


manager = MainManager()
app = manager.app
manager.start()
