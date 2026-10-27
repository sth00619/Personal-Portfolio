# 데이터 준비

이 프로젝트는 금융감독원 OpenDART API의 기업코드 아카이브, 공시목록, 접수번호별 XBRL 원본을 사용합니다. 인증키는 프로젝트 폴더의 `.env` 파일에만 저장합니다. 기업코드 아카이브와 선택한 접수번호별 XBRL 원본은 `data/`에 보존하며 Git에 추가하지 않습니다.

1. `.env.example`을 `.env`로 복사합니다.
2. `DART_API_KEY`에 OpenDART 발급 인증키를 입력합니다.
3. PostgreSQL을 실행한 뒤 `docker compose run --rm app`을 실행합니다.
4. `results/experiment.json`과 DB의 `disclosure_fact` 테이블에서 수집 건수, 정정 차이, PIT 결과를 확인합니다.

현재 실측 표본은 주식코드 031820 아이티센씨티에스의 분기 정정 사례입니다. 파이프라인은 해당 기업의 분기·반기·3분기 보고서를 조회하고 숫자 팩트 변경이 있는 원본·정정본 쌍을 선택합니다. 로컬 요청 상한은 `MAX_API_REQUESTS`로 조정할 수 있습니다.
