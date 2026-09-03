from dataclasses import dataclass
from enum import Enum
from typing import Any


class MessageType(Enum):
  ERROR = "error"
  EVENT = "event"
  FEEDBACK = "feedback"


class Event(Enum):
  Simulate = "simulate"
  Finish = "finish"


class WorkerName(Enum):
  Simulator = "simulator"
  GUI = "gui"


@dataclass
class Message:
  type: MessageType
  content: Any = None


if __name__ == "__main__":
  print(WorkerName.Simulator.value)
  print(type(WorkerName.Simulator.value))
