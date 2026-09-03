from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from queue import Queue

from dataclasses import dataclass
from typing import Any


@dataclass
class Message:
  type: str
  content: Any = None


class Worker(threading.Thread, ABC):
  def __init__(self, daemon: bool):
    super().__init__(daemon=daemon)

    self.message_queue = Queue()
    self._stop_event = threading.Event()

  def send(self, message: Message):
    self.message_queue.put(message)

  def stop(self):
    self._stop_event.set()

  @property
  def stopped(self):
    return self._stop_event.is_set()

  def run(self):
    try:
      self.send("event", "start")

      feedback = self.execute()

      if feedback is not None:
        self.send(Message("feedback", feedback))

    except Exception as e:
      self.send(Message("error", str(e)))

    finally:
      self.send(Message("event", "finish"))

  @abstractmethod
  def execute(self):
    raise NotImplementedError
