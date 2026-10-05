# 원본 데이터

프로젝트 폴더에서 다음 명령으로 공식 배포 파일을 받는다.

```bash
python data/download.py
```

- Solomon 100-customer VRPTW 인스턴스: SINTEF 백업 ZIP
- NYC TLC Yellow Taxi 월별 Trip Record: 픽업·도착 시각과 Taxi Zone 수요 패턴
- NYC TLC Taxi Zone 도형: 구역 대표 좌표 계산

원본은 `data/raw/` 아래에 저장되고 Git에서 제외된다. 다운로드 스크립트가 출력한 바이트 크기와 SHA-256으로 같은 입력인지 확인한다. TLC는 제출 사업자가 생성한 기록의 정확성·완전성을 보증하지 않는다고 안내한다. 시뮬레이션의 주문은 원본 행을 실제 배달 주문으로 간주하지 않고, 관측된 시간대·출발지·도착지·이동시간 분포에서 합성한다.
