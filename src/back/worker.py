from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from queue import Queue, Empty

from back.message import Message, MessageType, Event


class Worker(threading.Thread, ABC):
  def __init__(self, name):
    super().__init__(daemon=True, name=name)

    self._emit_message = Queue()
    self._received_message = Queue()
    self._stop_event = threading.Event()

    # self._emit(start)

  def _emit(self, message: Message):
    self._emit_message.put(message)

  def take_message(self) -> Message:
    try:
      return self._emit_message.get_nowait()
    except Empty:
      return None

  def receive_message(self, message):
    self._received_message.put(message)

  def stop(self):
    self._stop_event.set()

  @property
  def stopped(self):
    return self._stop_event.is_set()

  def run(self):
    while not self.stopped:
      try:
        feedback = self._handle_message()

        if feedback is not None:
          self._emit(Message(MessageType.FEEDBACK, feedback))

      except Exception as e:
        self._emit(Message(MessageType.ERROR, str(e)))

      self._stop_event.wait(0.05)  # 50ms

    self._finally_run()

  def _finally_run(self):
    pass

  @abstractmethod
  def _handle_message(self):
    raise NotImplementedError
