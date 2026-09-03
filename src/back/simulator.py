"""
설비 센서 시뮬레이터 (물리 기반)
CNC 밀링 설비 3대를 1분 단위로 시뮬레이션
- truth : 오염 없는 참값 (정답지)
- observed : 현장에서 실제로 받는 더러운 데이터

*CNC 밀링 설비 : 금속 같은 재료를 회전하는 절삭공구로 깍아서 원하는 형상으로 만드는 자동 가공 기계
"""

# 클래스가 만들어지기 전인데 반환 타입 User불가이기에 "User" 문자열 사용.
# class User:
#     def get_friend(self) -> "User":
# 파이썬 타입 힌트(annotation)를 바로 평가하지 않고 문자열 형태 저장.
# class User:
#     def get_friend(self) -> User:
from __future__ import annotations
import logging
import numpy as np
import pandas as pd
from queue import Empty

from message import MessageType, Message, Event, WorkerName
from worker import Worker

MACHINES = {
  # machine_id : (품질등급, 과부하 한계, 공구 교체주기(분))
  "CNC-01": {"type": "L", "osf_limit": 11000, "tool_life": 210},
  "CNC-02": {"type": "M", "osf_limit": 12000, "tool_life": 225},
  "CNC-03": {"type": "H", "osf_limit": 13000, "tool_life": 240},
}
# 관측 오염 강도 (기본값 = "현장급")
POLLUTION = {
  "dropout_rate": 0.015,  # 통신 끊김
  "dropout_len": (3, 40),  # 끊김 길이(분)
  "nan_rate": 0.008,  # 개별 센서값만 NaN
  "spike_rate": 0.004,  # 센서 튐(전기 노이즈)
  "dup_rate": 0.006,  # 같은 레코드 중복 전송
  "ts_jitter_rate": 0.05,  # 타임스탬프 흔들림
  "unit_mix_rate": 0.10,  # 단위 혼재(K 대신 섭씨)
  "drift_per_day": 0.35,  # 온도 센서 드리프트 (K/day)
}


class Simulator(Worker):
  def __init__(
    self, machine_id: str, n_minutes: int, start: pd.Timestamp, rng: np.random.Generator
  ):
    super().__init__(WorkerName.Simulator.value)
    self.logger = logging.getLogger()
    self.logger.info("Simulator Start")

    self.machine_id = machine_id
    self.time_start = start
    self.n_minutes = n_minutes
    self._rng = rng

  # n_minutes만큼 1분 간격으로 데이터 생성
  def _simulate_one(self, start, n_minutes, machine_id):
    spec = MACHINES[machine_id]

    ts = self._calculate_ts(start, n_minutes)
    hour = self._calculate_hours(ts)
    duty = self._calculate_dutys(hour, n_minutes)
    hvac = self._simulate_havc_fails(n_minutes)
    air = self._calculate_air(n_minutes, hvac)
    wear = self._calcuate_wear(n_minutes, spec["tool_life"], duty)
    rpm = self._calculate_rpm(n_minutes, duty)
    torque = self._calculate_torque(n_minutes, duty, wear)
    power_w = self._calculate_power_w(torque, rpm)
    process_temp = self._calculate_process_temp(n_minutes, air, power_w, wear, hvac)
    vib = self._caclulate_vibration(n_minutes, rpm, wear, spec["tool_life"])
    current = self._calculate_current(n_minutes, power_w)
    humid = self._calculate_humid(n_minutes, air)

    df = pd.DataFrame(
      {
        "ts": ts,
        "machine_id": machine_id,
        "type": spec["type"],
        "air_temp_k": air,
        "process_temp_k": process_temp,
        "rot_speed_rpm": rpm,
        "torque_nm": torque,
        "tool_wear_min": wear,
        "vibration_mms": vib,
        "current_a": current,
        "humidity_pct": humid,
      }
    )

    # ------------------------------------------------------------------
    # 고장 라벨 (AI4I 2020 정의 그대로)
    # ------------------------------------------------------------------
    twf = (wear >= 200) & (wear <= 240) & (self._rng.random(n_minutes) < 0.004)
    hdf = ((process_temp - air) < 8.6) & (rpm < 1380)
    pwf = (power_w < 3500) | (power_w > 9000)
    osf = (wear * torque) > spec["osf_limit"]
    rnf = self._rng.random(n_minutes) < 0.0002  # 원인 불명 랜덤 고장

    df["twf"] = twf.astype(int)
    df["hdf"] = hdf.astype(int)
    df["pwf"] = pwf.astype(int)
    df["osf"] = osf.astype(int)
    df["rnf"] = rnf.astype(int)
    df["machine_failure"] = (twf | hdf | pwf | osf | rnf).astype(int)
    df["power_w"] = power_w

    return df

  def _calculate_ts(self, start, n_minutes):
    # start부터 1분 간격으로 n_minutes개의 시간데이터
    return pd.date_range(start, periods=n_minutes, freq="min")

  def _calculate_hours(self, ts: pd.DatetimeIndex):
    # date_range를 실수 형태의 시간으로 변경
    return ts.hour + ts.minute / 60.0

  def _calculate_dutys(self, hour, n_minutes):
    # 부하를 주간과 야간으로 sin 함수로 변하도록 설정
    duty = 0.55 + 0.45 * np.sin((hour - 6) / 24 * 2 * np.pi)
    # 랜덤 노이즈 추가 후 0.05와 1.0으로 범위 제한
    return np.clip(duty + self._rng.normal(0, 0.05, n_minutes), 0.05, 1.0)

  # HAVC : Heating, Ventilation, and Air Conditioning. 공장의 난방/환기 공조 시스템
  def _simulate_havc_fails(self, n_minutes):
    # 분 길이만큼 bool타입 array
    havc_fail = np.zeros(n_minutes, dtype=bool)
    # 2000분마다 한번 정도 HVAC 고장 구간 생성
    for _ in range(max(1, n_minutes // 2000)):
      # HVAC 고장 최대 120분. 0부터 n_minutes - 120 구간 랜덤하게 고장 시작
      start = self._rng.integers(0, max(1, n_minutes - 120))
      # HVAC 고장이 40~119분 정도 지속
      havc_fail[start : start + self._rng.integers(40, 120)] = True
    return havc_fail

  def _calculate_air(self, n_minutes, hvac_fail):
    # air = 기준온도 + 하루동안온도변화
    air = 298.0 + 2.0 * np.sin((self._hour - 14) / 24 * 2 * np.pi)
    # 랜덤워크(누적된 랜덤값) 추가
    air = air + np.cumsum(self._rng.normal(0, 0.02, n_minutes))
    # 순간적 랜덤 노이즈 추가
    air = air + self._rng.normal(0, 0.15, n_minutes)

    return air + 5.5 * hvac_fail

  # wear : 각 분마다 공구 마모량
  def _calcuate_wear(self, n_minutes, tool_life, duty):
    # acc : 랜덤한 공구 마모량
    wear, acc = np.zeros(n_minutes), self._rng.uniform(0, 60)
    # 교체 시점은 정비반 재량. 툴 수명에 랜덤값 추가
    limit = tool_life * self._rng.uniform(0.90, 1.15)
    for i in range(n_minutes):
      # 기본적으로 매분 1.0만큼 닳고 duty에 따른 추가 마모
      acc += 1.0 + 0.6 * duty[i]
      # 공구의 마모량이 limit를 넘었을 때
      if acc > limit:
        # acc마모량 0.0. limit를 랜덤값 추가하면서 다시 세팅
        acc, limit = 0.0, tool_life * self._rng.uniform(0.90, 1.15)
      # 각 분마다 마모량 저장
      wear[i] = acc

    return wear

  def _calculate_rpm(self, n_minutes, duty):
    # rpm회전수는 부하가 낮으면 높음. 1150-2900사이로 제한
    return np.clip(2860 - 1500 * duty + self._rng.normal(0, 45, n_minutes), 1150, 2900)

  def _calculate_torque(self, n_minutes, duty, wear):
    # torque토크는 부하가 커지면 필요 토크 증가. 공구 마모가 증가되면 필요 토크 증가. 3-80사이로 제한.
    return np.clip(
      10 + 40 * duty + 0.02 * wear + self._rng.normal(0, 2.0, n_minutes), 3, 80
    )

  def _calculate_power_w(self, torque, rpm):
    # 전력 계산 : P(전력, W) = T(토크, N/m) * w(각속도, rad/s)
    # w = rpm * 2*pi / 60
    return torque * rpm * 2 * np.pi / 60.0  # T * w

  def _calculate_process_temp(self, n_minutes, air, power_w, wear, hvac):
    # 공정온도 = 공기온도 + 전력에의한열 + 마모(wera)에의한열 + 노이즈
    proc = air + 8.5 + power_w / 1400.0 + 0.004 * wear
    proc = proc - 6.0 * hvac
    return proc + self._rng.normal(0, 0.12, n_minutes)

  def _caclulate_vibration(self, n_minutes, rpm, wear, tool_life):
    # 진동 = 기본진동 + 회전에의한진동 + 마모에의한진동 + 노이즈
    # 마모에의한진동 = **3으로 공구 수명이 끝나갈수록 진동 빠르게 증가
    vib = (
      0.8
      + 0.0009 * rpm
      + 0.9 * (wear / tool_life) ** 3
      + self._rng.normal(0, 0.06, n_minutes)
    )
    return np.clip(vib, 0.1, None)

  def _calculate_current(self, n_minutes, power_w):
    # 3상 교류 전력 공식
    # P(전력) = 3**0.5 * V(선간전압)I(전류)cos(역률)
    current = power_w / (380 * 1.732 * 0.85) + self._rng.normal(0, 0.15, n_minutes)
    return np.clip(current, 0.2, None)

  def _calculate_humid(self, n_minutes, air):
    # --- 습도: 온도와 약한 음의 관계 ---
    humid = 55 - 1.8 * (air - 298) + self._rng.normal(0, 2.5, n_minutes)
    humid = np.clip(humid, 15, 95)

  def simulate_truth(self):
    pass

  def _handle_message(self):
    try:
      message: Message = self._received_message.get_nowait()

      feedback = None
      if message.type == MessageType.EVENT:
        if message.content == Event.Simulate:
          pass

      return feedback
    except Empty:
      return None
