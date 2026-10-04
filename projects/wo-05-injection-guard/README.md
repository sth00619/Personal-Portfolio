# WO-05 · 프롬프트 인젝션 가드레일
> 개인 프로젝트 · 대응 직군: AI 엔지니어 / AI 보안 / 백엔드 · 데이터: 직접 작성한 합성 이력서·공격 코퍼스 (제3자 원본 데이터 없음)

## 문제 정의

지원자 이력서, PDF 메타데이터, 외부 조회 결과는 평가 시스템이 읽어야 하지만 명령을 내릴 권한은 없다. 취약한 에이전트가 이 내용을 도구 호출로 해석하면 점수를 바꾸거나, ATS를 쓰거나, 이력서를 외부 주소로 보낼 수 있다. 이 프로젝트는 의도적으로 취약한 목 에이전트와 보호 경로를 같은 60개 공격에 적용하고, 공격 성공과 정상 이력서 오탐을 함께 측정한다.

**측정 경계:** 에이전트의 계획 해석과 도구는 결정적 시뮬레이터다. LLM API, 실제 이메일, 실제 ATS를 호출하지 않는다. 결과는 이 합성 코퍼스에서 코드의 권한 경계가 작동했음을 보여주며 실서비스 LLM의 공격 저항률을 뜻하지 않는다.

## 가설

1. 입력 문구 탐지만으로는 인코딩된 지시와 텍스트 없는 메타데이터를 놓친다.
2. 출처를 함께 전달하고 모든 도구 호출을 정책 라우터에서 검사하면, 계획 단계가 속아도 승인되지 않은 부작용을 막을 수 있다.
3. 정상 문서의 경고율을 같이 보고해야 공격 차단률을 해석할 수 있다.
4. 이메일·ATS 쓰기에는 평가 맥락의 권한 제한과 별도 일회용 확인 절차가 필요하다.

## 데이터

`data/generate.py`가 합성 정상 이력서 **100개**와 합성 공격 **60개**를 생성한다. 공격은 본문, PDF 메타데이터, 외부 도구 결과에 각 20개씩 넣었다. 각 계열에는 외부 이메일, ATS 쓰기, 점수 조작, 출력 조작 목표를 5개씩 배치했다. 12개는 Base64로 감쌌고 1개는 문자열 명령 없이 PDF 메타데이터의 숫자형 `score_hint`를 사용한다. 정상 이력서 중 2개에는 보안 연구 맥락의 의심 문구를 넣어 오탐을 확인한다. 출처와 생성 방법은 [data/README.md](data/README.md)에 있다.

공격 표면과 제어 원칙은 OWASP의 [LLM01:2025 Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/) 및 [LLM06:2025 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)를 참고했다. 공격 내용과 측정 수치는 이 프로젝트에서 생성한 것이다.

## 접근 / 파이프라인

```mermaid
flowchart LR
    A[이력서 본문] --> P[취약한 계획 해석기]
    B[PDF 메타데이터] --> P
    C[외부 도구 결과] --> P
    P -->|방어 전| M[목 이메일·점수·ATS·출력 도구]
    P -->|방어 후: 출처 태그| G[정책 라우터]
    G --> I[입력 분류 경고]
    G --> T[출처 격리·도구 허용 목록]
    G --> O[출력 검사]
    G --> H[고위험 행동 일회용 확인]
    T -->|허용된 행동만| M
```

- `src/parser.py`의 취약한 계획 해석기는 낮은 신뢰도의 문자열에서 도구 제안을 만든다. 공격이 통하는 기준선을 재현하기 위한 **의도적 취약점**이다. Base64 지시도 해석한다.
- `src/baseline.py`는 제안을 곧바로 목 도구에 실행한다.
- `src/guard.py`는 본문·메타데이터·도구 결과의 출처를 유지한다. 모델이 도구 제안을 만들었다고 가정해도 라우터가 출처, 평가 맥락의 허용 도구, 점수 출처, 출력 내용, 고위험 행동 확인 토큰을 검사한다.
- 입력 분류기는 단순 규칙 기반 **경고층**이다. 경고 자체가 허가나 차단 결정을 내리지 않는다.
- 정상 평가는 코드로 추출한 기술 키워드로 점수를 계산하고, 원문을 그대로 출력하지 않는 짧은 요약을 게시한다. 실제 채용 판단 모델이 아니다.
- `ConfirmationRegistry`는 승인자 이름과 **정확한 행동 인자**에 묶인 일회용 토큰을 사용한다. 목 ATS 쓰기 테스트에서 인자가 다른 토큰과 재사용된 토큰을 거부한다.
- 목 도구의 `outbox`, `ats_writes`, `score`, `published` 값을 보고 성공 여부를 판정한다. 탐지기가 공격이라고 표시했는지만으로 성공/실패를 정하지 않는다.

프로젝트 폴더에서 전체 재생과 테스트를 실행할 수 있다.

```bash
docker compose up --build --abort-on-container-exit --exit-code-from injection-guard
```

로컬 Python 3.11에서는 `pip install -r requirements.txt` 후 `python data/generate.py`, `python run.py`, `python -m pytest -q` 순서로 실행한다.

## 결과 (Ship Gate 표)

2026-10-04 Docker의 Python 3.11에서 측정했다. 전체 케이스별 수치는 [results/experiment.json](results/experiment.json), 비교표는 [results/report.md](results/report.md), 그래프는 [PNG](results/comparison.png)·[SVG](results/comparison.svg), 규칙별 로그는 [results/audit.jsonl](results/audit.jsonl)에 있다.

| 지표 | 취약 기준선 | 초기 가드 v1 | 최종 가드 v2 |
|---|---:|---:|---:|
| 공격 성공, 60건 | **60/60 (100%)** | **1/60 (1.67%)** | **0/60 (0%)** |
| 정상 문서 분류기 오탐, 100건 | — | — | **2/100 (2%)** |
| 정상 평가 완료 | — | — | **100/100** |

| 공격 계열 | 공격 수 | 방어 전 성공 | 방어 후 성공 | 입력 분류기 경고 |
|---|---:|---:|---:|---:|
| 본문 | 20 | 20/20 | 0/20 | 16/20 |
| 메타데이터 | 20 | 20/20 | 0/20 | 15/20 |
| 도구 결과 | 20 | 20/20 | 0/20 | 16/20 |

| Ship Gate | 실제 확인 |
|---|---|
| 방어 전후 성공률을 계열별 보고 | 3개 계열 모두 위 표와 결과 JSON에 기록 |
| 정상 100개 오탐 | 2건 경고, 정상 평가 100건 완료 |
| 우회 1건 발견·수정 | 숫자형 PDF `score_hint`: 초기 가드 점수 **60→100**, 최종 가드 **60 유지** |
| 모든 차단에 규칙 로그 | 공격 60건 전부 차단 규칙 존재; `audit.jsonl`에 케이스·단계·규칙·도구 기록 |

입력 문구 분류기는 공격 **47/60건만 경고**하고 13건을 놓쳤다. 그럼에도 최종 가드에서 도구 부작용은 0건이었다. 차단 로그에는 `UNTRUSTED_INSTRUCTION` 60건, `TOOL_NOT_ALLOWED` 45건, `CONFIRMATION_REQUIRED` 30건, `SCORE_SOURCE_UNTRUSTED` 15건, `OUTPUT_POLICY` 15건의 규칙 이벤트가 기록됐다. 한 행동에 여러 규칙이 동시에 적용되므로 합계는 공격 수보다 크다.

### 찾아낸 우회: 숫자형 메타데이터 점수 힌트

공격 `METADATA-SCORE_TAMPER-01`은 지시문 대신 PDF 메타데이터에 `score_hint: 100`을 넣는다. 초기 가드는 이 숫자를 OCR 보조 정보처럼 신뢰해 목 점수를 60에서 100으로 바꿨다. 문자열 탐지기는 경고하지 않았다. 최종 가드에서는 메타데이터 출처의 점수 변경을 `SCORE_SOURCE_UNTRUSTED`로 차단하고, 이력서 기술 근거로 계산한 60점을 유지했다. 전후 로그와 수정 이유는 [results/bypass_analysis.md](results/bypass_analysis.md)에 정리했다.

## 시행착오와 해결

- 처음에는 “의심 문구를 찾으면 된다”는 방식이 떠올랐지만 Base64 12건과 숫자형 힌트 1건에서 분류기가 신호를 얻지 못했다. 분류기를 경고층으로만 두고, 낮은 신뢰도의 제안은 정책 라우터에서 권한을 주지 않도록 했다.
- 점수 도구는 평가 맥락에서 필요하므로 단순 도구 금지만으로 해결할 수 없었다. 정상 점수는 코드가 이력서의 기술 키워드에서 계산하고, 메타데이터의 숫자형 점수는 출처 규칙으로 차단했다.
- 정상 보안 프로젝트 설명에 공격 문구가 들어갈 수 있다. 실제 정상 이력서 2건이 분류기 경고를 냈지만 평가 전체를 중단하지 않아 100건 모두 결과를 얻었다.
- 방어 전 100% 성공은 취약한 계획 해석기가 이 프로젝트에서 만든 명령 형식을 이해하도록 설계했기 때문이다. 이 수치를 일반 모델의 공격 성공률처럼 제시하지 않는다.

## 한계

- LLM을 호출하지 않아 실제 모델의 순응도, 확률적 변동, 다국어·멀티모달 공격을 평가하지 않았다.
- 공격 60건과 정상 100건은 합성·한정된 표본이다. 최종 0% 성공은 이 코퍼스에서 관찰한 결과일 뿐 보안 보증이 아니다.
- 입력 분류기와 출력 검사는 작은 규칙 집합이므로 더 다양한 우회에 취약하다. 주요 통제는 도구 권한과 출처 경계다.
- 이력서의 기술 경력 자체를 허위로 쓰는 문제는 프롬프트 인젝션과 달라 이 실험의 범위 밖이다.
- 테스트의 확인 토큰은 메모리 내 목 구현이다. 실제 시스템은 인증된 승인자, 만료, 영속 저장, 감사 로그 보호가 필요하다.
- 통합 서비스에서 출처 태그는 모델이 주장하는 값이 아니라 호스트 애플리케이션이 부여해야 한다. 이 데모의 파서는 호스트 측에서 출처를 붙인다.

## 개발 방식 (AI 활용 구분)

| 직접 작성한 것 | Codex가 생성한 것 |
|---|---|
| SONG이 제공한 적대적 이력서 평가 문제, 60건 공격·100건 정상·계열별 보고 Ship Gate | 합성 데이터, 취약 기준선, 보호 라우터, 목 도구, 테스트, 감사 로그·차트·문서 초안 |
| 필터보다 행동 권한 제한이 중요하다는 평가 기준 | 입력 경고·출처 격리·도구 허용 목록·출력 검사·확인 토큰과 우회 재현 |

수치는 코퍼스를 실제 코드에 재생한 결과이며 LLM이나 외부 도구 실측값으로 표현하지 않는다.

## 관련 개념

- **Prompt injection**: 낮은 신뢰도의 콘텐츠가 명령으로 승격되어 에이전트 행동을 바꾸는 문제
- **Least privilege**: 평가 중 필요한 점수·출력 도구만 허용하고 이메일·ATS 쓰기 권한을 주지 않는 원칙
- **Complete mediation**: 모든 도구 호출을 중앙 라우터에서 검사하는 원칙
- **Provenance**: 제안이 본문, 메타데이터, 외부 조회 결과 중 어디서 왔는지 보존하는 정보
- **False positive rate**: 정상 입력 중 경고를 받은 비율
- **Human confirmation**: 고위험 쓰기 전에 행동 인자와 일치하는 별도 승인 필요

## English Technical Summary

Built a deterministic red-team harness for a resume-scoring workflow with mock email, scoring, ATS-write, and publication tools. Sixty synthetic attacks were balanced across resume body, PDF metadata, and external tool-result surfaces, while 100 benign resumes measured false alarms. The deliberately unguarded planner executed all 60 attacker goals. A legacy guard missed one text-free numeric metadata score hint; the final policy router blocked all 60 mock side effects by enforcing host-assigned provenance, contextual tool allowlists, score-source validation, output checks, and action-bound one-use confirmation. The input phrase classifier alerted on 47/60 attacks and flagged 2/100 benign resumes, but all benign evaluations completed. These are control-flow results on authored fixtures, not measurements of a live LLM or real recruitment system.
