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
import numpy as np
import pandas as pd

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


def _simulate_one(
  machine_id: str, n_minutes: int, start: pd.Timestamp, rng: np.random.Generator
) -> pd.DataFrame:
  spec = MACHINES[machine_id]
  # start부터 1분 간격으로 n_minutes개의 시간 데이터
  ts = pd.date_range(start, periods=n_minutes, freq="min")

  # date_range를 실수 형태의 시간으로 변경
  hour = ts.hour + ts.minute / 60.0
  # 부하를 주간과 야간으로 sin함수로 변하도록 설정
  duty = 0.55 + 0.45 * np.sin((hour - 6) / 24 * 2 * np.pi)
  # 랜덤 노이즈 추가 후 0.05와 1.0으로 범위 제한
  duty = np.clip(duty + rng.normal(0, 0.05, n_minutes), 0.05, 1.0)

  # air = 기준온도 + 하루동안온도변화
  air = 298.0 + 2.0 * np.sin((hour - 14) / 24 * 2 * np.pi)
  # 랜덤워크(누적된 랜덤값) 추가
  air = air + np.cumsum(rng.normal(0, 0.02, n_minutes))
  # 순간적 랜덤 노이즈 추가
  air = air + rng.normal(0, 0.15, n_minutes)

  # wear : 각 분마다 공구 마모량
  # acc : 랜덤한 공구 마모량
  wear, acc = np.zeros(n_minutes), rng.uniform(0, 60)
  # 교체 시점은 정비반 재량. 툴 수명에 랜덤값 추가
  limit = spec["tool_life"] * rng.uniform(0.90, 1.15)
  for i in range(n_minutes):
    # 기본적으로 매분 1.0만큼 닳고 duty에 따른 추가 마모
    acc += 1.0 + 0.6 * duty[i]
    # 공구의 마모량이 limit를 넘었을 때
    if acc > limit:
      # acc마모량 0.0. limit를 랜덤값 추가하면서 다시 세팅
      acc, limit = 0.0, spec["tool_life"] * rng.uniform(0.90, 1.15)
    # 각 분마다 마모량 저장
    wear[i] = acc

  # rpm회전수는 부하가 낮으면 높음. 1150-2900사이로 제한
  rpm = np.clip(2860 - 1500 * duty + rng.normal(0, 45, n_minutes), 1150, 2900)
  # torque토크는 부하가 커지면 필요 토크 증가. 공구 마모가 증가되면 필요 토크 증가. 3-80사이로 제한.
  torque = np.clip(10 + 40 * duty + 0.02 * wear + rng.normal(0, 2.0, n_minutes), 3, 80)

  # 분 길이만큼 bool타입 array
  hvac_fail = np.zeros(n_minutes, dtype=bool)
  # 2000분마다 한번 정도 HVAC고장 구간 생성
  for _ in range(max(1, n_minutes // 2000)):
    # HVAC 고장 최대 120분. 0부터 n_minutes - 120 구간 랜덤하게 고장 시작
    s = rng.integers(0, max(1, n_minutes - 120))
    # HVAC 고장이 40~119분 정도 지속
    hvac_fail[s : s + rng.integers(40, 120)] = True
  # air, hvac_fail의 크기 = (n_minutes, )
  air = air + 5.5 * hvac_fail

  # 전력 계산 : P(전력, W) = T(토크, N/m) * w(각속도, rad/s)
  # w = rpm * 2*pi / 60
  power_w = torque * rpm * 2 * np.pi / 60.0  # T * w
  # 공정온도 = 공기온도 + 전력에의한열 + 마모(wera)에의한열 + 노이즈
  proc = air + 8.5 + power_w / 1400.0 + 0.004 * wear
  proc = proc - 6.0 * hvac_fail
  proc = proc + rng.normal(0, 0.12, n_minutes)

  # 진동 = 기본진동 + 회전에의한진동 + 마모에의한진동 + 노이즈
  # 마모에의한진동 = **3으로 공구 수명이 끝나갈수록 진동 빠르게 증가
  vib = (
    0.8
    + 0.0009 * rpm
    + 0.9 * (wear / spec["tool_life"]) ** 3
    + rng.normal(0, 0.06, n_minutes)
  )
  vib = np.clip(vib, 0.1, None)

  # 3상 교류 전력 공식
  # P(전력) = 3**0.5 * V(선간전압)I(전류)cos(역률)
  current = power_w / (380 * 1.732 * 0.85) + rng.normal(0, 0.15, n_minutes)
  current = np.clip(current, 0.2, None)

  # --- 습도: 온도와 약한 음의 관계 ---
  humid = 55 - 1.8 * (air - 298) + rng.normal(0, 2.5, n_minutes)
  humid = np.clip(humid, 15, 95)

  df = pd.DataFrame(
    {
      "ts": ts,
      "machine_id": machine_id,
      "type": spec["type"],
      "air_temp_k": air,
      "process_temp_k": proc,
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
  twf = (wear >= 200) & (wear <= 240) & (rng.random(n_minutes) < 0.004)
  hdf = ((proc - air) < 8.6) & (rpm < 1380)
  pwf = (power_w < 3500) | (power_w > 9000)
  osf = (wear * torque) > spec["osf_limit"]
  rnf = rng.random(n_minutes) < 0.0002  # 원인 불명 랜덤 고장

  df["twf"] = twf.astype(int)
  df["hdf"] = hdf.astype(int)
  df["pwf"] = pwf.astype(int)
  df["osf"] = osf.astype(int)
  df["rnf"] = rnf.astype(int)
  df["machine_failure"] = (twf | hdf | pwf | osf | rnf).astype(int)
  df["power_w"] = power_w
  return df
