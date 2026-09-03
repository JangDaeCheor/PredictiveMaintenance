import warnings

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt


KOREAN_FONT_CANDIDATES = [
  "AppleGothic",
  "Malgun Gothic",
  "NanumGothic",
  "NanumBarunGothic",
]


def find_korean_font():
  """현재 환경에 설치된 한글 폰트를 반환한다."""
  installed_fonts = {font.name for font in fm.fontManager.ttflist}
  return next(
    (font for font in KOREAN_FONT_CANDIDATES if font in installed_fonts),
    None,
  )


def test_korean_font_rendering():
  """그래프의 한글 글리프가 빠짐없이 렌더링되는지 확인한다."""
  font_name = find_korean_font()
  if font_name is None:
    raise AssertionError(
      "한글 폰트를 찾지 못했습니다. 다음 중 하나를 설치하세요: "
      + ", ".join(KOREAN_FONT_CANDIDATES)
    )

  with plt.rc_context({"font.family": font_name, "axes.unicode_minus": False}):
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [3, 1, 2], label="설비 온도")
    ax.set_title("한글 폰트 렌더링 테스트")
    ax.set_xlabel("시간")
    ax.set_ylabel("측정값")
    ax.legend()

    try:
      with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        fig.canvas.draw()

      missing_glyph_warnings = [
        warning
        for warning in caught_warnings
        if "Glyph" in str(warning.message)
        and "missing from font" in str(warning.message)
      ]
      assert not missing_glyph_warnings, "한글 글리프가 누락되었습니다: " + "; ".join(
        str(warning.message) for warning in missing_glyph_warnings
      )
    finally:
      plt.close(fig)


def show_korean_font_test_graph():
  """한글 표시 상태를 눈으로 확인할 수 있는 테스트 그래프를 띄운다."""
  font_name = find_korean_font()
  if font_name is None:
    raise RuntimeError(
      "한글 폰트를 찾지 못했습니다. 다음 중 하나를 설치하세요: "
      + ", ".join(KOREAN_FONT_CANDIDATES)
    )

  plt.rcParams["font.family"] = font_name
  plt.rcParams["axes.unicode_minus"] = False

  x_values = [-3, -2, -1, 0, 1, 2, 3]
  temperatures = [-5, -2, 1, 4, 7, 5, 3]

  fig, ax = plt.subplots(figsize=(9, 5))
  ax.plot(x_values, temperatures, marker="o", label="설비 온도")
  ax.set_title("한글 폰트 표시 테스트: 가나다라")
  ax.set_xlabel("경과 시간")
  ax.set_ylabel("측정 온도 (℃)")
  ax.legend(title="범례")
  ax.grid(alpha=0.3)
  fig.tight_layout()

  print(f"사용 중인 한글 폰트: {font_name}")
  print("그래프에서 제목, 축 이름, 범례, 음수 기호가 정상인지 확인하세요.")
  plt.show()


if __name__ == "__main__":
  test_korean_font_rendering()
  show_korean_font_test_graph()
