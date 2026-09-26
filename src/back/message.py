from dataclasses import dataclass
from enum import Enum
from typing import Any

from datetime import date
from pydantic import BaseModel


class SimulatorRequest(BaseModel):
  start: date
  n_minutes: int


class MessageType(Enum):
  ERROR = "error"
  EVENT = "event"
  FEEDBACK = "feedback"


class Event:
  SimulateTruth = "simulate_truth"
  DBInsert = "db_insert"
  DBUpdate = "db_update"
  DBDelete = "db_delete"
  DBSelect = "db_select"
  Error = "error"

  def __init__(self, event, content: dict):
    self.event = event
    self.content = content

  # def toJsonString(self):
  #   return json.dumps(self, default=lambda o: o.__dict__, indent=4)


class WorkerName(Enum):
  Simulator = "simulator"
  GUI = "gui"
  MainManager = "mainmanager"
  DB = "db"


class Status(Enum):
  Running = "running"
  Failed = "failed"
  Completed = "completed"
  Non = "none"


@dataclass
class Message:
  id: int
  type: MessageType
  status: str
  content: Any = None


if __name__ == "__main__":
  print(WorkerName.Simulator.value)
  print(type(WorkerName.Simulator.value))
