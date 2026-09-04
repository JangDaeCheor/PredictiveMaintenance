import socket
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
FASTAPI_HOST = "127.0.0.1"
FASTAPI_PORT = 8000


def wait_for_fastapi(process: subprocess.Popen, timeout: float = 10.0) -> None:
  deadline = time.monotonic() + timeout

  while time.monotonic() < deadline:
    if process.poll() is not None:
      raise RuntimeError(f"FastAPI가 종료되었습니다. 종료 코드: {process.returncode}")

    try:
      with socket.create_connection((FASTAPI_HOST, FASTAPI_PORT), timeout=0.2):
        return
    except OSError:
      time.sleep(0.1)

  raise TimeoutError(f"FastAPI가 {timeout}초 안에 시작되지 않았습니다.")


def stop_process(process: subprocess.Popen | None) -> None:
  if process is None or process.poll() is not None:
    return

  process.terminate()
  try:
    process.wait(timeout=5)
  except subprocess.TimeoutExpired:
    process.kill()
    process.wait()


def main() -> None:
  fastapi_process = None
  streamlit_process = None

  try:
    fastapi_process = subprocess.Popen(
      [
        sys.executable,
        "-m",
        "uvicorn",
        "back.manager:app",
        "--app-dir",
        str(SRC_DIR),
        "--host",
        FASTAPI_HOST,
        "--port",
        str(FASTAPI_PORT),
      ],
      cwd=PROJECT_ROOT,
    )
    wait_for_fastapi(fastapi_process)

    streamlit_process = subprocess.Popen(
      [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(SRC_DIR / "front" / "app.py"),
      ],
      cwd=PROJECT_ROOT,
    )

    while True:
      fastapi_code = fastapi_process.poll()
      streamlit_code = streamlit_process.poll()

      if fastapi_code is not None:
        raise RuntimeError(f"FastAPI가 종료되었습니다. 종료 코드: {fastapi_code}")
      if streamlit_code is not None:
        break

      time.sleep(0.2)
  except KeyboardInterrupt:
    print("\n서버를 종료합니다.")
  finally:
    stop_process(streamlit_process)
    stop_process(fastapi_process)


if __name__ == "__main__":
  main()
