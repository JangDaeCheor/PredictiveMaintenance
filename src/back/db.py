import sqlite3
from pathlib import Path
import pandas as pd
from queue import Empty

from back.worker import Worker
import back.message as ms

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sensors.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SENSOR_RAW_COLUMNS = (
  "machine_id",  # 설비 식별자.
  "ts",  # 센서 측정 시각. ISO8601 문자열 (UTC 기준)
  "type",  # 설비 또는 제품 유형.
  "air_temp_k",  # 주변 공기 온도. 단위는 켈빈(K)
  "process_temp_k",  # 공정 온도. 단위는 켈빈(K)
  "rot_speed_rpm",  # 회전 속도. 단위는 RPM
  "torque_nm",  # 토크. 단위는 N/m
  "tool_wear_min",  # 공구 누적 마모 시간. 단위는 분
  "vibration_mms",  # 진동 속도. 단위는 mm/s
  "current_a",  # 설비에 흐르는 전류. 단위는 암페어(A)
  "humidity_pct",  # 상대습도. 단위는 백분율
  "machine_failure",  # 설비 고장 여부. 일반적으로 0은 정상. 1은 고장
)


class DB(Worker):
  def __init__(self):
    super().__init__(ms.WorkerName.DB.value)
    self.conn = None
    self.cursor = None
    # self.conn = sqlite3.connect(DB_PATH)
    # self.cursor = self.conn.cursor()

  def create(self):
    CREATE = """
    CREATE TABLE IF NOT EXISTS sensor_raw (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,  -- 행 고유번호. 데이터 삽입 시 자동 증가
        machine_id      TEXT    NOT NULL,
        ts              TEXT    NOT NULL,
        collected_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
        type            TEXT,
        air_temp_k      REAL,
        process_temp_k  REAL,
        rot_speed_rpm   REAL,
        torque_nm       REAL,
        tool_wear_min   REAL,
        vibration_mms   REAL,
        current_a       REAL,
        humidity_pct    REAL,
        machine_failure INTEGER,
        UNIQUE (machine_id, ts)                    -- ★ 중복 방어선
    );

    CREATE INDEX IF NOT EXISTS ix_sensor_ts      ON sensor_raw (ts);
    """
    with self.conn:
      self.conn.executescript(CREATE)

  def _select(
    self,
    machine_id: str | None = None,
    ts: tuple[str | pd.Timestamp, str | pd.Timestamp] | None = None,
  ) -> pd.DataFrame:
    """장비 ID와 측정 시간 범위로 센서 데이터를 조회한다."""
    if self.conn is None:
      raise RuntimeError("데이터베이스에 연결되어 있지 않습니다.")

    conditions = []
    params = []

    if machine_id is not None:
      conditions.append("machine_id = ?")
      params.append(machine_id)

    if ts is not None:
      if not isinstance(ts, tuple) or len(ts) != 2:
        raise ValueError("ts는 (시작 시각, 종료 시각) 튜플이어야 합니다.")

      start, end = (pd.Timestamp(value) for value in ts)
      if start > end:
        raise ValueError("ts의 시작 시각은 종료 시각보다 늦을 수 없습니다.")

      conditions.append("ts BETWEEN ? AND ?")
      params.extend((start.isoformat(), end.isoformat()))

    sql = "SELECT * FROM sensor_raw"
    if conditions:
      sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY id ASC"

    if machine_id is None and ts is None:
      sql += " LIMIT 5"

    return pd.read_sql_query(sql, self.conn, params=params)

  def _delete(
    self,
    machine_id: list[str],
    ts: list[str | pd.Timestamp],
  ) -> int:
    """machine_id와 ts 쌍에 해당하는 센서 데이터 여러 행을 삭제한다."""
    if self.conn is None:
      raise RuntimeError("데이터베이스에 연결되어 있지 않습니다.")

    if not isinstance(machine_id, list) or not isinstance(ts, list):
      raise TypeError("machine_id와 ts는 list여야 합니다.")

    if len(machine_id) != len(ts):
      raise ValueError("machine_id와 ts의 개수가 같아야 합니다.")

    if not machine_id:
      return 0

    if any(pd.isna(value) for value in machine_id) or any(
      pd.isna(value) for value in ts
    ):
      raise ValueError("machine_id와 ts에는 빈 값을 사용할 수 없습니다.")

    sql = "DELETE FROM sensor_raw WHERE machine_id = ? AND ts = ?"
    rows = (
      (
        self._to_sqlite_value(machine_id_value),
        self._to_sqlite_value(ts_value),
      )
      for machine_id_value, ts_value in zip(machine_id, ts)
    )

    before = self.conn.total_changes
    with self.conn:
      self.cursor.executemany(sql, rows)
    return self.conn.total_changes - before

  def _update(self, df: pd.DataFrame) -> int:
    """machine_id와 ts가 일치하는 센서 데이터를 여러 행 갱신한다."""
    if self.conn is None:
      raise RuntimeError("데이터베이스에 연결되어 있지 않습니다.")

    if not isinstance(df, pd.DataFrame):
      raise TypeError("df는 pandas.DataFrame이어야 합니다.")

    if not df.columns.is_unique:
      raise ValueError("DataFrame에 중복된 컬럼 이름이 있습니다.")

    missing = [column for column in SENSOR_RAW_COLUMNS if column not in df.columns]
    if missing:
      raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing)}")

    if df.empty:
      return 0

    if df.loc[:, ["machine_id", "ts"]].isna().any(axis=None):
      raise ValueError("machine_id와 ts에는 빈 값을 사용할 수 없습니다.")

    key_columns = {"machine_id", "ts"}
    update_columns = [
      column for column in SENSOR_RAW_COLUMNS if column not in key_columns
    ]
    assignments = ", ".join(f"{column} = ?" for column in update_columns)
    sql = f"UPDATE sensor_raw SET {assignments} WHERE machine_id = ? AND ts = ?"

    parameter_columns = update_columns + ["machine_id", "ts"]
    rows = (
      tuple(self._to_sqlite_value(value) for value in row)
      for row in df.loc[:, parameter_columns].itertuples(index=False, name=None)
    )

    before = self.conn.total_changes
    with self.conn:
      self.cursor.executemany(sql, rows)
    return self.conn.total_changes - before

  def _insert(self, df: pd.DataFrame) -> int:
    """센서 데이터프레임을 저장하고 실제로 추가된 행 수를 반환한다."""
    if self.conn is None:
      raise RuntimeError("데이터베이스에 연결되어 있지 않습니다.")

    if not isinstance(df, pd.DataFrame):
      raise TypeError("df는 pandas.DataFrame이어야 합니다.")

    missing = [column for column in SENSOR_RAW_COLUMNS if column not in df.columns]
    if missing:
      raise ValueError(f"필수 컬럼이 없습니다: {', '.join(missing)}")

    if df.empty:
      return 0

    columns = ", ".join(SENSOR_RAW_COLUMNS)
    placeholders = ", ".join("?" for _ in SENSOR_RAW_COLUMNS)
    sql = f"INSERT OR IGNORE INTO sensor_raw ({columns}) VALUES ({placeholders})"

    rows = []
    selected_df = df.loc[:, SENSOR_RAW_COLUMNS]  # 특정 col 선택
    for row in selected_df.itertuples(index=False, name=None):  # 각 행 순회
      converted_row = []
      for value in row:
        converted_value = self._to_sqlite_value(value)
        converted_row.append(converted_value)
      rows.append(tuple(converted_row))

    before = self.conn.total_changes
    with self.conn:
      self.cursor.executemany(sql, rows)
    return self.conn.total_changes - before

  def _to_sqlite_value(self, value):
    if pd.isna(value):
      return None
    if isinstance(value, pd.Timestamp):
      return value.isoformat()
    # sqlite3가 처리할 수 있도록 numpy 스칼라를 Python 스칼라로 변환한다.
    if hasattr(value, "item"):
      return value.item()
    return value

  def _finally_run(self):
    if self.conn is not None:
      self.conn.close()

  def _handle_message(self):
    if self.conn is None:
      self.conn = sqlite3.connect(DB_PATH)
      self.cursor = self.conn.cursor()
      self.create()

    try:
      message: ms.Message = self._received_message.get_nowait()

      feedback = None
      if message.type == ms.MessageType.EVENT:
        if message.content.event == ms.Event.DBInsert:
          feedback = self._insert(message.content.content)
        elif message.content.event == ms.Event.DBSelect:
          feedback = self._select(
            message.content.content["machine_id"], message.content.content["ts"]
          )
        elif message.content.event == ms.Event.DBDelete:
          feedback = self._delete(
            message.content.content["machine_id"], message.content.content["ts"]
          )
        elif message.content.event == ms.Event.DBUpdate:
          feedback = self._update(message.content.content)

      return feedback
    except Empty:
      return None
    except KeyError as e:
      self._emit(ms.Message(ms.MessageType.ERROR, e))
      return None
