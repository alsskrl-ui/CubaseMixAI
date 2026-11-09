# CubaseMixAI

Cubase 10.5용 로컬 믹싱 도우미입니다. **WAV 분석 → DSP/CLAP 비교 → 변경안 → 브라우저 직접 승인 → MIDI 적용 → Cubase 재렌더 가져오기 → A/B 평가**를 제공합니다.

자동 검증과 실제 사용자 환경의 검증은 구분합니다. **사용자에게 남은 일은 [설정·검증 체크리스트](docs/verification-checklist.md)** 에 모았습니다. [구현 범위](docs/roadmap.md) · [테스트 기록](docs/validation.md)

## 설치와 실행

Python 3.11 이상을 사용합니다. [Windows/Cubase 설치 안내](docs/windows-cubase.md)를 함께 보세요.

```sh
git clone https://github.com/alsskrl-ui/CubaseMixAI.git
cd CubaseMixAI
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -e '.[dev]'
cubasemixai doctor
cubasemixai ui
```

`http://127.0.0.1:8765`를 열어 UI 실행 터미널의 토큰을 입력하세요. 파일 경로로 분석·백업·변경안 생성·승인·미리보기·실제 전송·복원·재렌더 비교·A/B 출력을 실행할 수 있습니다. 토큰은 AI에게 전달하지 마세요. 모든 처리는 로컬에서 수행하며 음원을 외부로 업로드하지 않습니다. AI 설치 시에는 공식 모델 파일을 다운로드합니다.

## WAV · 스템 · 후렴/드롭 분석

```sh
cubasemixai analyze mix.wav --start 30 --end 60
cubasemixai compare mix.wav reference.wav
cubasemixai stems stems.json
cubasemixai sections mix.wav reference.wav sections.json
```

`stems.json`은 `{"kick":"C:/audio/kick.wav","808":"C:/audio/808.wav","vocal":"C:/audio/vocal.wav","guitar":"C:/audio/guitar.wav"}` 형태입니다. 직접 내보낸 스템을 사용하며 음원 분리 모델은 포함하지 않습니다.

`sections.json` 예:

```json
[{"name":"chorus","start":30,"end":50,"reference_start":40,"reference_end":60},
 {"name":"drop","start":65,"end":80,"reference_start":70,"reference_end":85}]
```

LUFS(pyloudnorm), RMS, sample peak, 4× 오버샘플링 true-peak **추정**, crest, 400ms RMS 분포, 대역 에너지, 상관 및 side/mid를 측정합니다. 무음의 dB는 JSON `null`입니다. True peak는 인증 계측기가 아니고 블록 RMS 분포는 EBU LRA가 아닙니다. mono/stereo WAV, 8kHz 이상, 선택 구간당 0.4초–15분을 지원합니다. 렌더가 끝난 파일을 분석하세요.

## 실측 MIDI 매핑

`config/mapping.example.json`은 설명용 수치이므로 그대로 사용하지 마세요. Generic Remote/QC에서 측정한 점으로 교체해야 합니다.

```sh
cubasemixai ports
cubasemixai calibrate measurements.local.json config/mapping.local.json --confirmed-measured
cubasemixai calibration-check config/mapping.local.json observations.local.json
```

측정 파일은 `{"port":"CubaseMixAI","controls":{...}}` 구조이며, 각 제어는 channel(1–16), cc(0–127), unit, max_delta, points가 필요합니다. points는 `[[표시된 물리값, CC 정수], ...]`로 양쪽 모두 엄격히 증가해야 합니다. 예시 수치를 검증 완료로 바꾸는 것은 실제 측정을 대신하지 못합니다. 생성 명령은 기존 파일을 덮어쓰지 않습니다. 독립 관측 예:

```json
[{"control":"vocal.volume","requested":-2,"observed":-2.1,"tolerance":0.2}]
```

제어 이름은 다음 규칙을 사용합니다. 플러그인의 EQ 주파수/Q와 comp attack/release는 먼저 수동 설정하고 각 파라미터의 단위를 확인하세요. 실제 노출되는 제어만 등록하며 누락된 것은 자동으로 건너뜁니다.

| 제어 이름 예 | 단위 | 역할 |
|---|---|---|
| `vocal.volume`, `master.volume` | dB | 트랙/마스터 레벨 |
| `master.eq.bass.gain` | dB | 해당 EQ 대역 gain (`sub/bass/low_mid/mid/presence/air`) |
| `master.compressor.threshold` | dB | 컴프레서 threshold |
| `master.compressor.ratio` | ratio | 컴프레서 ratio |
| `master.compressor.attack`, `.release` | ms | 수동 설정·명시적 제안으로 조절 |
| `master.limiter.ceiling` | dB | 실제 limiter의 출력 ceiling |

대역 경계는 분석용 범위입니다. 물리 EQ의 정확한 주파수/Q와 일치한다고 가정하지 마세요. 코드가 플러그인의 주파수나 gain을 자동으로 읽지는 않습니다.

## 변경안 · 로컬 승인 · 복원

```sh
# current.local.json 예: {"master.volume":0,"master.eq.bass.gain":0,"master.compressor.threshold":-12}
cubasemixai reference-plan mix.wav reference.wav config/mapping.local.json current.local.json --mode master
# 개별 스템은 같은 종류의 레퍼런스 스템과 비교합니다.
cubasemixai reference-plan vocal.wav vocal-reference.wav config/mapping.local.json vocal-current.local.json --target vocal
cubasemixai apply PROPOSAL_ID
# UI에서 백업과 현재 값을 확인하고 직접 승인한 뒤에만:
cubasemixai apply PROPOSAL_ID --live
cubasemixai restore PROPOSAL_ID
cubasemixai history
```

판단 엔진은 DSP 휴리스틱으로 EQ gain·볼륨·컴프레서 threshold/ratio·limiter ceiling 수치 후보를 만듭니다. EQ는 작은 보정, 볼륨은 레퍼런스 LUFS와 추정 peak 여유, 컴프레서는 crest 차이를 근거로 삼습니다. mapped control의 변화량 한계와 실측 범위, MIDI 정수 해상도를 지킵니다. 제안에는 이유/위험/보정되지 않은 신뢰도와 원본 분석을 기록합니다. 학습된 전문 믹싱 판단을 보장하지 않습니다.

기본 apply는 dry-run입니다. live는 로컬 승인, 생성 후 15분 이내, 동일 매핑·근거 WAV를 요구합니다. 승인 하나로 실제 전송은 한 번만 시도합니다. 부분 실패는 `uncertain`, 전송 중 종료는 `sending`으로 남고 자동 재시도하지 않습니다. `simulation: true` 매핑은 승인해도 live 전송할 수 없습니다.

이력은 `.cubasemixai/history.sqlite3`, 적용 전 사용자 입력 스냅샷은 `<id>.before.json`입니다. **사용자 입력값은 DAW readback이 아니며 MIDI 전송 성공도 Cubase 적용 확인이 아닙니다.** `restore`는 역방향 pending 제안을 만들고 재승인이 필요합니다. 부분 적용 뒤에는 실제 현재 값을 다시 확인해 새 제안을 만드세요.

## CLAP 청취 엔진

```sh
# CPU용 PyTorch를 먼저 설치하면 불필요한 GPU 의존성 설치를 피할 수 있습니다.
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e '.[ai]'
cubasemixai setup-ai .cubasemixai/models/clap
cubasemixai listen mix-clip.wav reference-clip.wav .cubasemixai/models/clap
cubasemixai reference-plan mix-clip.wav reference-clip.wav config/mapping.local.json current.local.json --model-dir .cubasemixai/models/clap
```

setup-ai는 공식 `laion/clap-htsat-unfused`의 고정 revision을 기록하여 다운로드하고 torch 2.6+의 `weights_only=True`로 로드한 뒤 safetensors로 저장합니다. 추론 시 다운로드하지 않습니다. 새 빈 모델 폴더를 사용하고 충분한 디스크 공간을 확보하세요(모델 약 590MB, 설치 과정 추가 공간 필요).

0.4–30초 WAV에서 최대 10초씩 시작/중간/끝의 결정적 window를 사용하고 레벨을 정규화합니다. 음원 임베딩 유사도와 밝기·펀치·잔향/공간 프롬프트 친화도, window spread를 계산합니다. stereo는 에너지가 더 큰 채널을 분석하며 스테레오 폭은 DSP 결과로 확인합니다. 의미적 유사도는 품질 점수가 아니고 신뢰도는 확률이 아닙니다. DSP·CLAP 근거의 파일 해시가 다르면 통합을 거부합니다. 수치 후보는 DSP에 기반하고 CLAP을 검토 근거 및 충돌 차단에 사용합니다. 충분한 window 근거가 있는 밝기·펀치 결과가 DSP 보정 방향과 충돌하면 관련 EQ/컴프레서 후보를 보류합니다. CLAP이 직접 임의의 제어값을 정하지 않습니다.

## 프로젝트 백업 · 마스터 체인 · 재렌더

```sh
# Cubase에서 외부 미디어를 모으고 저장·종료한 뒤 실행
cubasemixai backup C:/Projects/TestMix C:/Backups/TestMix-001
cubasemixai verify-backup C:/Backups/TestMix-001
cubasemixai restore-project C:/Backups/TestMix-001 C:/Restored/TestMix-001
cubasemixai master-chain config/mapping.local.json
cubasemixai render-start before.wav reference.wav C:/Exports/after-001.wav
# Cubase에서 안내된 새 경로에 같은 locator/sample rate/channels로 WAV 내보내기
cubasemixai render-finish JOB_ID --model-dir .cubasemixai/models/clap
cubasemixai evaluate before.wav after.wav reference.wav --model-dir .cubasemixai/models/clap
cubasemixai ab before.wav after.wav C:/Exports/ab-001
cubasemixai report analysis.json report.html
```

백업은 `.cpr`이 있는 폴더를 SHA-256으로 검증하며 복원은 새 폴더만 허용합니다. 폴더 밖의 미디어는 Cubase Back up Project로 먼저 모으세요. symlink/junction과 변경 중인 소스는 거부합니다.

마스터 버스의 EQ → compressor → true-peak limiter 삽입과 WAV 내보내기는 Cubase에서 직접 수행합니다. Generic Remote에는 임의 플러그인 삽입/Export 실행/전체 상태 조회 API가 없습니다. `master-chain`은 필요한 매핑과 수동 설정을 알려주고 `--mode master`는 작은 변경 후보를 만듭니다.

재렌더 비교는 전후 형식·길이·원본 해시를 확인하고 LUFS 오차·대역거리·crest·추정 peak·선택적 CLAP 재청취를 기록합니다. 통계가 레퍼런스에 가까워져도 품질 개선을 자동 확정하지 않습니다. A/B 출력은 같은 목표 LUFS와 공통 peak 여유를 사용한 FLOAT WAV로, 최종 마스터나 리미팅 결과가 아닙니다. 출력 폴더/HTML은 기존 파일을 덮어쓰지 않습니다.

## Codex MCP 등록

Cubase가 설치된 Windows에서 실행합니다. CLI/UI/MCP가 작업 디렉터리와 관계없이 같은 상태를 쓰도록 절대 경로를 지정하세요.

```powershell
codex mcp add cubasemixai --env CUBASEMIXAI_STATE_DIR=C:\CubaseMixAI\.cubasemixai -- C:\CubaseMixAI\.venv\Scripts\cubasemixai-mcp.exe
codex mcp list
C:\CubaseMixAI\.venv\Scripts\cubasemixai.exe --state-dir C:\CubaseMixAI\.cubasemixai ui
```

22개 도구: analyze/compare/analyze_stems/recommend/integrate/propose_reference/evaluate_render/compare_sections/export_ab/export_report/clap_compare/backup_project/verify_backup/restore_project/calibration_report/master_chain/create_render_job/finish_render_job/propose/apply/history/restore.

approve/decide/raw MIDI 도구는 없습니다. 서버는 로컬 사용자 권한으로 파일을 읽고 명시한 새 출력 경로에 쓸 수 있습니다. 로컬 토큰은 동일 사용자 권한의 악의적 프로그램에 대한 보안 경계가 아닙니다. UI는 loopback에만 바인딩하고 token/Host/Origin을 검증합니다.

## 개발 검증

```sh
python -m pytest -q
OMP_NUM_THREADS=2 python scripts/validate_ai.py .cubasemixai/models/clap
python -m pip install -e '.[browser]'
python -m playwright install chromium
python scripts/validate_browser.py
```

Windows PowerShell에서 스레드 제한이 필요하면 `$env:OMP_NUM_THREADS="2"`를 먼저 실행합니다. 브라우저 테스트 전에는 8765 포트의 UI를 종료하세요. 테스트는 임시 음원과 시뮬레이션 매핑을 사용하며 실기기에 MIDI를 보내지 않습니다. `requirements-tested.txt`는 초기 Linux Python 3.12의 버전 기록이며 범용 잠금 파일이 아닙니다. [최신 환경·검증 기록](docs/validation.md)을 참고하세요.
