# 데이터 준비

`python data/download.py`는 [Figshare의 iPinYou season 2 보관본](https://figshare.com/articles/dataset/ipinyou_contest_dataset_season2/5732328)에서 검증된 ZIP 내부 범위만 내려받는다. 원래 배포처는 [iPinYou 공식 페이지](https://contest.ipinyou.com/data-release.html)이며, 원본의 이용 조건인 **비상업 사용**을 따른다. Figshare의 CC0 표시는 원 배포자의 이용 조건을 대체하는 근거로 사용하지 않는다.

학습·보정에는 각 날짜의 압축 `imp` 파일 앞 16 MiB만 사용한다. 따라서 파일 끝의 미완성 BZip2 블록과 미완성 행은 버린다. 재생 평가에는 마지막 날짜의 `imp` 파일 전체와 해당 `clk` 로그를 사용한다. 클릭 로그는 네 날짜 모두 전체 파일을 받는다. `data/raw/`와 원본 ZIP은 Git에서 제외한다.

범위와 SHA-256/MD5 값은 `download.py`에 고정했다. 전체 파일의 MD5는 원본 `files.md5`와 대조했고, 접두 구간의 SHA-256은 내려받은 바이트에 대해 기록했다.
