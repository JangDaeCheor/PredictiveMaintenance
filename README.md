# 설비 예지보전(Predictive Maintenance)

1. 센서 파이프라인
  - 물리 기반 센서 시뮬레이터 (온도, 습도, 진동, 전류, 마모)
  - 수집기 (스케줄러) => CSV + SQLite 적재
  - 정제 파이프라인 => 참값과 대조 검증
2. 실데이터로 함정 확인 - 공개 벤치마크
  - UCI AI4I 2020 (설비 예지보전, 10000행, 고장률 3.39%)
  - UCI SECOM (반도체 공정, 590센서, 불량률 6.64%)
3. 자동화/배포
  - GitHub Actions로 매일 자동 수집 (공개 저장소 무료)
  - Streamlit Community Cloud로 대시보드 배포 (무료)
  - README + 분석 리포트

# UCI AI4I 2020 데이터셋 고장 정의

1. TWF(Tool Wear Failure, 공구 마모 고장) : 마모 200~240분 구간에서 확률적으로 발생
2. HDF(Heat Dissipation Failure, 방열 실패) : (공정온도 - 공기온도) < 8.6K 그리고 회전수 < 1380rpm
3. PWF(Power Failure, 전력 이상) : 전력이 3500W 미만 또는 9000W 초과
4. OSF(Overstrain Failure, 과부하) : 마모x토크 > 임계값 (등급별 11000/12000/13000)
5. RNF(Random Failure, 원인 불명) : 무작위 (센서로 예측 불가능)
