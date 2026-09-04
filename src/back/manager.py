from fastapi import FastAPI, APIRouter


class MainManager:
  def __init__(self):
    self.app = FastAPI()
    self.router = APIRouter()

    self.router.add_api_route(
      "/simulate",
      self.simulate,
      methods=["GET"],
    )

    self.app.include_router(self.router)

  def simulate(self):
    return [
      {"온도": 72.1, "진동": 3.2, "회전수": 1420},
      {"온도": 73.5, "진동": 3.5, "회전수": 1430},
      {"온도": 71.8, "진동": 3.1, "회전수": 1415},
    ]


manager = MainManager()
app = manager.app
