# CubaseMixAI

Cubase 10.5에서 **WAV 분석 → 근거 검토 → 변경안 → 로컬 승인 → MIDI 제어 → 재렌더 비교**를 수행하는 Python MVP입니다. Generic Remote를 사용하며 Cubase 내부 상태를 자동으로 읽지 않습니다.

실제 Windows/Cubase 연결, CLAP 모델 실행, 마스터 체인 청취 검증은 아직 수행하지 않았습니다. DSP 수치를 AI가 들은 결과로 표시하지 않으며, 마스터링을 자동 완성했다고 주장하지 않습니다.

## 시작

Python 3.11 이상이 필요합니다. Windows는 [설치 및 Cubase 연결](docs/windows-cubase.md)을 먼저 읽으세요. Linux에서는 오디오 분석과 모의 MIDI 테스트를 실행할 수 있습니다.

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -e '.[dev]'
cubasemixai analyze mix.wav
cubasemixai compare mix.wav reference.wav
python -m pytest -q
```

측정: integrated LUFS(pyloudnorm), sample peak, 4배 오버샘플링 true-peak **추정**, RMS, crest, 400ms RMS 분포, 대역 에너지 비율, 좌우 상관, side/mid 비율. 무음의 dB 값은 JSON `null`입니다. True peak는 인증 계측기가 아니며 RMS 분포는 EBU LRA가 아닙니다. 전체 파일 또는 구간 하나는 최대 15분입니다.

후렴/드롭은 같은 음악 구간끼리 별도 시작/종료 시간을 지정하세요. Python/MCP의 `compare`는 믹스와 레퍼런스에 서로 다른 구간을 지정할 수 있습니다. `analyze_stems`는 kick/808/vocal/guitar로 **직접 내보낸 스템**을 분석합니다. 스템 분리 기능은 없습니다.

## MIDI 변경 및 승인

1. `config/mapping.example.json`을 `config/mapping.local.json`으로 복사합니다. 예시 CC/dB 값은 실제 Cubase 캘리브레이션이 아닙니다.
2. Cubase에서 매핑과 값을 측정하고 `points`를 교체한 후 `verified: true`로 지정합니다. 채널은 설정 파일에서 1–16, mido 내부에서는 0–15입니다.
3. `changes.json`에 직접 확인한 현재 값과 목표 값을 기록합니다.

```json
[{"control":"vocal.volume","before":0,"after":-2,"unit":"dB"}]
```

```sh
cubasemixai ports
cubasemixai propose config/mapping.local.json changes.json --reason "보컬 레벨 A/B 테스트"
cubasemixai ui
# 별도 터미널: 우선 미리보기
cubasemixai apply PROPOSAL_ID
# 브라우저에서 직접 검토/승인한 다음에만 실제 전송
cubasemixai apply PROPOSAL_ID --live
cubasemixai history
cubasemixai restore PROPOSAL_ID
```

UI는 `http://127.0.0.1:8765`에만 바인딩합니다. UI 실행 터미널의 토큰을 브라우저에 입력하세요. 승인 토큰을 Codex/다른 에이전트에 제공하지 마세요. 승인 API는 MCP에 노출되지 않습니다. 승인 시 백업과 현재 값을 확인해야 합니다. 제안은 생성 후 15분 동안 유효하고 매핑 파일 해시가 바뀌면 새 제안이 필요합니다. 승인 하나로 실제 전송은 한 번만 시도합니다. 실패·부분 전송은 `uncertain`, 전송 중 프로세스 종료는 `sending`으로 남으며 자동 재시도하지 않습니다.

`.cubasemixai/history.sqlite3`에 이력, `<id>.before.json`에 적용 전 입력값을 저장합니다. **이 스냅샷은 Cubase 프로젝트 백업이나 실제 상태 readback이 아닙니다.** `restore`는 역방향 변경안을 만들며 다시 현재 값 확인과 승인이 필요합니다. MIDI 전송 성공은 Cubase 적용 확인이 아니므로 귀와 화면으로 검증하세요.

## 판단 및 선택적 AI

`recommend(compare(...))`는 피크 헤드룸 조절 후보와 대역/crest 차이에 대한 검토 항목을 생성합니다. EQ 주파수·게인과 컴프레서 attack/release/ratio를 전체 믹스 통계만으로 단정하지 않으므로 실행 값은 사용자가 정합니다. Generic Remote에 매핑한 EQ/컴프레서 Quick Control은 단위, 측정 포인트, 변화량 한계를 설정해 같은 승인 경로로 제어할 수 있습니다.

```sh
python -m pip install -e '.[ai]'
cubasemixai listen mix-clip.wav reference-clip.wav /path/to/trusted-clap-checkpoint.pt
```

CLAP은 선택 사항입니다. 신뢰할 수 있는 LAION CLAP non-fusion 체크포인트를 별도로 준비하세요. 모델/가중치를 자동 다운로드하지 않습니다. 현재 CPU 경로, 각 30초 이하 클립을 지원하며 첫 실행은 오래 걸릴 수 있습니다. CLAP/torch/torchaudio 호환성은 대상 PC에서 검증해야 합니다. 코사인 유사도는 의미적 유사성으로, 음색·펀치·공간의 품질 점수가 아닙니다. 본 환경에서 CLAP 설치와 추론은 검증하지 않았습니다.

## MCP / Codex

프로젝트와 가상환경이 있는 **Windows PC**에서 등록하세요. 이 클라우드의 MCP 등록은 Windows Cubase에 연결되지 않습니다.

```powershell
codex mcp add cubasemixai -- C:\path\CubaseMixAI\.venv\Scripts\cubasemixai-mcp.exe
codex mcp list
```

MCP를 실행하는 작업 디렉터리를 프로젝트 루트로 맞추세요. CLI UI와 MCP는 같은 작업 디렉터리의 `.cubasemixai`를 사용해야 합니다. 도구: `analyze`, `compare`, `analyze_stems`, `recommend`, `propose`, `apply`, `history`, `restore`. `apply` 기본값은 dry-run입니다. `approve` 도구는 없습니다. 파일 경로는 로컬 경로로 전달하며 이 서버는 로컬 사용자 권한으로 파일을 읽습니다. 로컬 UI 토큰은 같은 사용자 권한을 가진 악의적 프로그램에 대한 보안 경계가 아닙니다.

## 마스터링 및 검증

작업 복사본에서 마스터 EQ → compressor → limiter 순으로 체인을 직접 구성합니다. 레퍼런스의 LUFS를 무조건 목표로 삼지 말고 장르·다이내믹과 플랫폼을 고려하세요. Generic Remote에서 노출되지 않는 플러그인 파라미터는 수동 조작합니다. Cubase에서 같은 구간/샘플레이트로 WAV를 다시 내보낸 다음 `compare`를 반복하고, 출력 레벨을 맞춘 A/B 청취로 개선 여부를 판단하세요. 이 MVP는 Cubase 재렌더를 자동 실행하지 않습니다.

[단계별 진행 상태 및 수락 기준](docs/roadmap.md)
