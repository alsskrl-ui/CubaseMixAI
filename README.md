# CubaseMixAI 0.4 사용 매뉴얼

Cubase 15의 MIDI Remote DirectAccess 또는 Cubase 10.5의 기존 CC 경로로, 레퍼런스를 분석하고 직접 승인한 변경만 적용하는 로컬 프로그램입니다. 이 문서는 **Cubase가 설치된 Windows PC + PowerShell + Codex CLI**를 기준으로 작성했습니다.

기본 순서는 다음과 같습니다.

**Cubase에서 WAV 내보내기 → 프로그램/Codex로 분석 → 변경안 생성 → 브라우저에서 직접 승인 → MIDI 적용 → Cubase에서 새 WAV 내보내기 → 전후 비교·청취**

첫 사용은 MIDI 설정 없이 WAV 분석부터 시작할 수 있습니다. Cubase 페이더나 플러그인을 실제로 움직이려면 loopMIDI와 실측 매핑 설정을 마쳐야 합니다.

## Cubase 15를 쓴다면 먼저

**[Cubase 15 전용 연결·Codex 사용 가이드](docs/cubase15.md)** 를 따르세요. 0.3에서 양방향 DirectAccess 드라이버를 추가했습니다. 노출된 대상은 CC 수동 매핑 대신 실제 트랙/플러그인 identity와 현재 값을 읽어 제안하고, 적용 후 다시 읽어 확인합니다. API 1.3의 물리값 변환·설치 플러그인 catalog·빈 슬롯 삽입을 feature detection으로 지원합니다.

[API·오픈소스 조사 근거](docs/cubase15-api-research.md)에는 공식 문서, 참고 저장소, MCU/VST3/OSC 등의 대안과 선택 이유를 정리했습니다. **새 backend는 자체 mock/프로토콜 테스트를 거쳤고 실제 Cubase 15 검증은 아직 필요합니다.** 이전 CC 가이드는 Cubase 10.5용 경로로 유지합니다.

### Cubase 15에서 할 수 있는 일

| 기능 | 동작 | 예시 |
|---|---|---|
| 상태 조회 | 실제 트랙·파라미터와 현재 값을 읽음 | “Kick 트랙의 Volume 값을 보여줘.” |
| 믹스 조정 | 노출된 파라미터에 변경안을 만들고, 로컬 UI에서 승인한 뒤 적용·재조회 | “Kick이 너무 튀어. 현재 Volume보다 1 dB 낮춘 안을 만들어줘. 아직 적용하지 마.” |
| 플러그인 확인·삽입 | API가 지원하면 설치 목록을 보고 **빈 Insert 슬롯**에 선택한 플러그인을 승인 후 삽입 | “빈 슬롯과 설치 플러그인을 보여줘. 아직 삽입하지 마.” |
| WAV 분석·비교 | 내보낸 믹스/스템의 음량·주파수·다이내믹·스테레오 및 선택적 CLAP 비교 | “믹스와 킥 스템을 분석하고 차이를 설명해줘.” |
| MIDI 표현 추가 | MIDI 클립의 새 복사본에 제한된 피치벤드·모듈레이션(CC1)·채널 애프터터치 생성 | “이 MIDI를 복사해서 피치가 최대 6센트 정도 천천히 흔들리는 버전을 만들어줘.” |

믹서 조정은 **조회 → 제안 → 로컬 UI에서 직접 승인 → 적용 → Cubase 값 재확인 → 새 WAV를 내보내 청취** 순서입니다. MIDI 표현 도구는 악기 파트의 MIDI 파일이 있어야 하며, WAV 스템에는 연주 이벤트가 남아 있지 않아 적용할 수 없습니다. 원본 클립을 바꾸지 않고 새 `.mid`를 만들며, Cubase로 가져와 악기 트랙에 연결해 직접 들어본 뒤 사용하세요. 피치벤드와 채널 애프터터치는 같은 MIDI 채널의 동시 발음 음 모두에 영향을 줍니다. 파라미터 노출과 플러그인 삽입은 Cubase 빌드/API 기능에 따라 다릅니다. 자동 WAV 렌더, 기존 플러그인 교체·삭제, 최종 음질 판정은 지원하지 않습니다. Cubase 15 DirectAccess 실기기 연결은 아직 확인되지 않았습니다.

CLI 예: `cubasemixai midi-expression source.mid expressive.mid --pitch-wander-cents 6 --pitch-bend-range-semitones 2`. [MIDI 표현 사용법](docs/cubase15.md#midi-expression)에서 CC1·애프터터치 예시와 import 절차를 확인하세요.

자세한 연결 절차는 [Cubase 15 빠른 시작과 제한사항](docs/cubase15.md)을, 나머지 설치·분석·Cubase 10.5 CC 사용법은 아래 매뉴얼을 참고하세요.

## 목차

- [Cubase 15: 실제 상태 조회와 승인 후 DirectAccess 제어](docs/cubase15.md)

- [1. 프로그램과 Codex의 역할](#roles)
- [2. Windows 설치와 프로젝트 준비](#install)
- [3. 프로그램 실행과 첫 WAV 분석](#first-run)
- [4. Cubase·loopMIDI 연결과 실측 매핑](#midi)
- [5. Codex에 로컬 MCP 서버 등록](#mcp)
- [6. Codex와 함께 사용하는 실제 예시](#codex-usage)
- [7. 승인·적용·복원 방법](#approval)
- [8. CLAP AI 청취 설치와 사용](#clap)
- [9. 스템·후렴·드롭 분석](#sections)
- [10. 백업·마스터링·재렌더·A/B 청취](#mastering)
- [11. 매일 사용하는 순서와 업데이트](#daily)
- [12. 오류 해결](#troubleshooting)
- [13. 파일·상태·MCP 도구 목록과 검증 범위](#reference)

<a id="roles"></a>
## 1. 프로그램과 Codex의 역할

| 구성 요소 | 실행 위치 | 역할 |
|---|---|---|
| Cubase 15 또는 10.5 | 사용자 Windows PC | 원본 프로젝트, 믹서, 플러그인, WAV 내보내기 |
| loopMIDI | 같은 Windows PC | Python에서 Cubase로 MIDI CC를 전달하는 가상 포트 |
| CubaseMixAI CLI | PowerShell | WAV 분석, 변경안, 백업, 재렌더 비교 등의 명령 실행 |
| 로컬 승인 UI | 같은 PC의 웹 브라우저 | 결과 확인, 변경안 직접 승인·거절, 실제 전송, 복원 제안 |
| CubaseMixAI MCP 서버 | Codex가 실행하는 로컬 프로세스 | Codex가 프로그램의 29개 도구를 호출하도록 연결 |
| Codex CLI | 같은 Windows PC | 자연어 요청을 도구 호출로 바꾸고 결과·근거·다음 작업 설명 |
| CLAP | 선택 설치, 같은 PC | 음원 임베딩과 음색·펀치·공간 프롬프트 친화도 비교 |

**이 README의 로컬 MCP 등록은 ChatGPT 앱의 GitHub 연결 설정과 별개입니다.** GitHub 연결은 소스코드 접근에 사용하고, 로컬 MCP는 설치된 프로그램을 실행하는 데 사용합니다. 스마트폰 ChatGPT나 클라우드 Codex에 등록해도 Windows PC의 Cubase가 자동으로 연결되지는 않습니다.

이 매뉴얼은 Windows PowerShell에서 직접 실행하는 Codex CLI를 기준으로 합니다. WSL/Linux에서 실행하는 Codex는 파일 경로와 MIDI 백엔드가 다릅니다. 처음에는 Windows의 Python·Codex·loopMIDI를 같은 환경에서 실행하세요. 다른 Codex 클라이언트의 설정 메뉴는 버전에 따라 다를 수 있으며, 등록 후 실제 MCP 도구 호출로 연결을 확인해야 합니다.

기존 CC 경로의 현재 값은 사용자가 화면에서 확인해 입력합니다. Cubase 15 DirectAccess 경로는 API가 노출한 실제 객체/파라미터를 조회하고, API 1.3 plugin manager가 있으면 빈 슬롯 삽입도 승인 후 수행합니다. 모든 plugin/내부 상태가 노출된다고 가정하지 않으며 WAV 내보내기와 최종 청취는 직접 합니다.

<a id="install"></a>
## 2. Windows 설치와 프로젝트 준비

### 2-1. 먼저 설치할 프로그램

| 프로그램 | 권장 준비 | 설치 후 확인 |
|---|---|---|
| Python | 3.11 x64, 설치 시 Python launcher 포함 | `py -3.11 --version` |
| Git for Windows | 공식 설치 프로그램 | `git --version` |
| Node.js | LTS, npm 포함 | `node --version`, `npm --version` |
| Codex CLI | 아래 npm 명령으로 설치 | `codex --version` |
| loopMIDI | Tobias Erichsen 공식 배포판 | 앱에서 포트 생성 후 CLI로 확인 |
| Cubase | 15 DirectAccess 또는 기존 10.5 CC용 테스트 프로젝트 | 작업 복사본이 정상적으로 열리는지 확인 |

다운로드: [Python](https://www.python.org/downloads/windows/) · [Git](https://git-scm.com/downloads/win) · [Node.js](https://nodejs.org/) · [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)

설치 후 PowerShell을 새로 열고 실행합니다.

```powershell
py -3.11 --version
git --version
node --version
npm --version
npm install -g @openai/codex
codex --version
```

`codex` 명령을 실행하면 안내에 따라 로그인합니다. Codex 계정·네트워크 연결은 WAV 측정 엔진과 별개이며, Codex를 사용하지 않고 프로그램만 실행하는 것도 가능합니다.

`npm.ps1` 또는 `codex.ps1` 실행 정책 오류가 나면 같은 명령의 `npm.cmd`, `codex.cmd`를 사용하세요. 예: `npm.cmd install -g @openai/codex`. 이 매뉴얼은 가상환경 활성화 스크립트를 실행하지 않아도 사용할 수 있게 작성했습니다.

### 2-2. 소스코드 받기와 가상환경 만들기

이하 예제의 설치 위치는 **`C:\CubaseMixAI`** 입니다. 다른 폴더를 사용하면 명령의 경로를 실제 설치 위치로 바꿉니다. 이미 저장소를 받은 경우에는 다시 clone하지 말고 그 폴더로 이동하세요.

```powershell
git clone https://github.com/alsskrl-ui/CubaseMixAI.git C:\CubaseMixAI
Set-Location C:\CubaseMixAI
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e .
```

기본 설치만으로 DSP 분석·UI·MIDI·MCP를 사용할 수 있습니다. CLAP은 [8장](#clap)의 추가 설치가 필요합니다. 개발 테스트까지 실행하려면 `-e .` 대신 `-e '.[dev]'`를 사용하세요.

Python 3.11이 설치되어 있다면 `scripts/setup-windows.ps1`로 가상환경과 개발 의존성을 설치할 수도 있습니다. 위 수동 명령과 둘 중 한 방법을 선택하면 됩니다.

### 2-3. 이후 명령에서 사용할 경로 정하기

각 PowerShell 창에서 다음을 한 번 실행합니다. **새 창을 열면 변수는 다시 지정해야 합니다.**

```powershell
Set-Location C:\CubaseMixAI
$App = 'C:\CubaseMixAI\.venv\Scripts\cubasemixai.exe'
$State = 'C:\CubaseMixAI\.cubasemixai'
$env:CUBASEMIXAI_STATE_DIR = $State
New-Item -ItemType Directory -Force C:\CubaseMixAI\audio | Out-Null
New-Item -ItemType Directory -Force C:\CubaseMixAI\exports | Out-Null
```

`& $App ...`는 설치한 프로그램을 실행하는 PowerShell 문법입니다. `$State`는 변경안·승인·이력·재렌더 작업이 저장되는 공용 폴더입니다. 나중에 Codex MCP에도 **같은 절대 경로**를 등록합니다.

### 2-4. 설치 확인

```powershell
& $App doctor
& $App --help
```

`doctor`에서 `python_supported`, `tools`, `midi`, `ai_dependencies`, `state_dir`를 확인합니다. CLAP을 아직 설치하지 않았다면 AI 의존성이 `false`여도 기본 분석은 사용할 수 있습니다. loopMIDI를 아직 만들지 않았다면 MIDI 출력 목록이 비어 있을 수 있습니다.

<a id="first-run"></a>
## 3. 프로그램 실행과 첫 WAV 분석

### 3-1. 음원 준비

1. Cubase에서 테스트 프로젝트의 믹스를 WAV로 내보냅니다.
2. 비교할 레퍼런스도 WAV로 준비합니다. MP3를 파일명만 `.wav`로 바꾸면 안 됩니다.
3. 아래 예제처럼 파일을 배치합니다.

```text
C:\CubaseMixAI\audio\mix.wav
C:\CubaseMixAI\audio\reference.wav
```

mono/stereo WAV, 8kHz 이상을 지원합니다. DSP는 선택 구간당 0.4초–15분, CLAP은 파일당 0.4초–30초입니다. 첫 연습은 같은 음악적 역할을 하는 10–20초 구간을 내보내 사용하세요. 전후 A/B 파일은 길이·샘플레이트·채널 수를 같게 내보냅니다.

### 3-2. CLI로 분석하기

```powershell
& $App analyze C:\CubaseMixAI\audio\mix.wav
& $App compare C:\CubaseMixAI\audio\mix.wav C:\CubaseMixAI\audio\reference.wav
```

결과는 터미널에 JSON으로 표시됩니다. 이 두 명령은 MIDI를 보내지 않습니다. 전체 파일 중 특정 구간만 분석하려면 다음과 같이 초 단위를 지정합니다.

```powershell
& $App analyze C:\CubaseMixAI\audio\mix.wav --start 30 --end 50
```

| 결과 항목 | 읽는 방법 |
|---|---|
| `lufs_i` | 구간 전체의 integrated loudness. 일반적으로 값이 덜 음수일수록 더 큼 |
| `rms_dbfs` | 평균 신호 에너지 수준 |
| `sample_peak_dbfs` | 샘플 값의 최대 크기 |
| `true_peak_estimate_dbtp` | 4× 오버샘플링 peak 추정. 최종 마스터는 별도 true-peak 미터로 확인 |
| `crest_db` | peak와 RMS의 차이. transient와 다이내믹을 검토하는 보조 지표 |
| `bands_percent` | 각 대역의 상대 에너지 비율. 그대로 EQ 목표값으로 해석하지 않기 |
| `stereo` | 좌우 상관과 side/mid 비율 |
| `mix_minus_reference` | 믹스 수치에서 레퍼런스 수치를 뺀 차이 |

무음의 dB 값은 `null`입니다. 블록 RMS 분포는 EBU LRA가 아니며 레퍼런스에 수치가 가까워지는 것만으로 좋은 믹스라고 판정하지 않습니다.

### 3-3. 승인 UI 열기

**PowerShell 창 A**에서 실행하고 창을 열어둡니다.

```powershell
& $App --state-dir $State ui
```

터미널에 다음과 같은 안내가 표시됩니다.

```text
Local review: http://127.0.0.1:8765
State directory: C:\CubaseMixAI\.cubasemixai
Review token (do not share with an AI agent): ...
```

1. 같은 PC의 브라우저에서 **http://127.0.0.1:8765** 를 엽니다.
2. 터미널의 `Review token` 값을 상단 입력칸에 직접 붙여넣습니다. 이 토큰을 Codex 대화에 보내지 않습니다.
3. `수행할 작업`에서 **믹스 / 레퍼런스 분석**을 선택합니다.
4. 두 WAV의 절대 경로를 입력하고 **실행**을 누릅니다.
5. **작업 결과**에서 분석을 확인하고 필요하면 **결과 JSON 저장**으로 내려받습니다.

이 UI는 loopback 전용입니다. 스마트폰 브라우저의 `127.0.0.1`은 스마트폰 자신을 가리키므로 Windows UI에 연결되지 않습니다. 프로그램을 중지하려면 창 A에서 `Ctrl+C`를 누릅니다. 재실행하면 새 토큰을 입력해야 하며 기존 이력은 같은 상태 폴더에 남습니다.

UI에서 제공하는 작업은 분석·구간/스템 비교·AI 청취·변경안·백업·캘리브레이션 오차 확인·마스터 매핑 점검·재렌더 가져오기·A/B 출력입니다. UI의 일반 변경안 생성 폼은 DSP 기반입니다. CLAP 근거까지 통합한 제안은 [6장](#codex-usage)의 Codex 예시 또는 [8장](#clap)의 CLI 명령을 사용합니다.

<a id="midi"></a>
## 4. Cubase 10.5: loopMIDI·Generic Remote 연결과 실측 매핑

이 장의 목표는 **① 킥 볼륨 하나를 먼저 움직여 보고 ② 킥 컴프레서/EQ까지 연결하는 것**입니다. WAV 분석만 할 때는 건너뛰어도 됩니다. 처음부터 모든 스템과 플러그인을 연결하지 말고 킥 한 트랙에서 확인한 뒤 늘려가세요.

### 4-1. MIDI CC가 무엇이고 어디에 연결하는가

CC는 숫자로 된 제어 메시지입니다. 다음 세 가지를 구분하세요.

| 항목 | 예 | 의미 |
|---|---|---|
| MIDI Channel | `1` | 메시지를 구분하는 채널. 킥 오디오 트랙 번호가 아님 |
| CC 번호/Address | `21` | 어떤 조절기를 움직일지 구분하는 주소 |
| CC 값/Value | `64` | 해당 조절기의 위치, 0–127 정수. 64가 0dB라는 뜻은 아님 |

프로그램에서 `채널 1 / CC21 / 값 64`를 보내면, Cubase 설정이 **CC21을 킥 Volume으로 연결**하고 있어야 킥 페이더가 움직입니다. WAV에 MIDI CC를 넣는 방식이 아니라 **Cubase의 믹서/플러그인 파라미터를 제어**하는 방식입니다. 오디오 스템을 MIDI 트랙으로 바꿀 필요가 없습니다.

이 매뉴얼에서는 두 연결 방식을 사용합니다.

| 조절 대상 | Cubase에서 연결할 곳 | 대상이 정해지는 방식 |
|---|---|---|
| 킥·808·보컬 등 트랙 Volume | Generic Remote | 아래 표에서 지정한 트랙을 대상에 연결 |
| 킥 플러그인의 threshold·ratio·EQ gain | Track Quick Controls | 현재 선택한 트랙의 Quick Control 슬롯을 제어 |

**Track Quick Controls는 선택한 트랙에 따라 대상이 달라집니다.** 설정 파일에 `kick.compressor.threshold`라고 써도 Cubase가 자동으로 킥 트랙을 선택해 주지는 않습니다. 플러그인 제어는 한 트랙씩 진행하며, 제안 생성부터 실제 적용이 끝날 때까지 그 트랙을 선택해 둡니다.

Cubase 10.5의 메뉴/항목 이름은 언어·에디션에 따라 다를 수 있습니다. 아래는 일반적인 영문 표기를 병기한 절차이며, 실제 대상과 동작은 사용자 Cubase에서 확인해야 합니다. Cubase 12 이후의 MIDI Remote 화면 대신 **Generic Remote / Track Quick Controls**를 사용합니다.

### 4-2. loopMIDI 포트와 테스트 프로젝트 준비

1. Cubase에서 **File → Back up Project**로 미디어가 포함된 별도 작업 복사본을 만듭니다.
2. loopMIDI를 실행합니다.
3. 새 포트 이름에 **CubaseMixAI**를 입력하고 `+` 버튼으로 추가합니다.
4. 목록에 포트가 나타났는지 확인하고 loopMIDI를 켜둡니다.
5. Cubase를 실행해 작업 복사본을 엽니다. 이미 켜져 있었고 포트가 보이지 않는다면 Cubase를 다시 실행합니다.
6. 킥 스템이 있는 오디오 트랙 이름을 알아보기 쉽게 **Kick**으로 정합니다.
7. PowerShell에서 프로그램이 해당 출력을 찾는지 확인합니다.

```powershell
$App = 'C:\CubaseMixAI\.venv\Scripts\cubasemixai.exe'
& $App ports
```

출력 목록의 **정확한 포트 문자열**을 기록합니다. 드라이버가 접미사를 붙여 `CubaseMixAI 0`처럼 표시한다면 프로그램의 JSON `port`와 아래 수동 테스트 코드에서도 그 문자열을 사용합니다. Cubase의 드롭다운 표기와 Python 목록의 표기가 완전히 같다고 가정하지 마세요.

### 4-3. Cubase MIDI Port Setup 설정

1. Cubase 상단 메뉴 **Studio → Studio Setup**을 엽니다.
2. 왼쪽 **MIDI Port Setup**을 선택합니다.
3. `CubaseMixAI` 입력 포트를 찾습니다.
4. 이 입력의 **In 'All MIDI Inputs'** 체크를 해제합니다. 원격 제어 CC가 일반 악기 트랙의 연주 입력으로 섞이는 것을 막기 위한 설정입니다.
5. 포트 자체를 비활성화하지는 않습니다. 다음 단계에서 remote 입력으로 선택할 수 있어야 합니다.

포트가 목록에 없다면 여기서 다른 설정을 추측하기보다 loopMIDI 실행 여부 → 포트 생성 → Cubase 재시작 순서로 확인합니다.

<a id="kick-volume"></a>
### 4-4. 킥 볼륨: Generic Remote 장치 추가

1. 같은 **Studio Setup** 창에서 장치 추가 `+` 메뉴를 엽니다.
2. **Generic Remote**를 선택합니다.
3. 왼쪽 목록에서 방금 추가한 Generic Remote를 선택합니다.
4. 오른쪽의 **MIDI Input**을 loopMIDI의 `CubaseMixAI` 포트로 지정합니다.
5. **MIDI Output**은 피드백을 사용하지 않는 첫 설정에서는 **Not Connected**로 둡니다.

실물 MIDI 컨트롤러가 없으므로 **Learn에 의존하지 않고 숫자를 직접 입력**해도 됩니다. 이 화면은 보통 위·아래 두 표로 나뉩니다.

- **위쪽 표**: 어떤 MIDI 메시지를 받을지 설정합니다.
- **아래쪽 표**: 받은 메시지로 Cubase의 무엇을 조절할지 설정합니다.

### 4-5. 위쪽 표: 킥 볼륨용 CC21 등록

기존 제어 행 하나를 사용하거나 행을 추가해 다음처럼 설정합니다.

| 위쪽 표 항목 | 입력할 예시 | 설명 |
|---|---|---|
| Control Name | `Kick Volume` | 알아보기 위한 제어 이름 |
| MIDI Status | `Controller` / `Control Change` | CC 메시지를 받는 타입. Note On을 고르지 않음 |
| MIDI Channel | `1` | 프로그램 JSON의 channel 1과 일치 |
| Address | `21` | 킥 볼륨에 배정할 CC 번호 |
| Max. Value | `127` | 일반 7-bit CC 범위 |
| Flags | `Receive` / `R` 활성화 | 입력을 받도록 설정 |

Flags 선택창에 Receive/Transmit/Relative 등이 보이면 첫 설정은 **Receive만 사용하고 Transmit·Relative는 사용하지 않습니다.** CC의 절대 위치를 보내는 예제입니다. 아래쪽 동작의 Button/Toggle 같은 버튼 모드도 Volume에는 사용하지 않습니다.

여러 Generic Remote 장치에서 같은 포트·채널·CC를 동시에 받도록 설정하지 마세요. 예전 설정이 있다면 CC21이 다른 항목에도 할당되어 있지 않은지 확인합니다.

### 4-6. 아래쪽 표: CC21을 실제 Kick 트랙 Volume에 연결

위에서 만든 `Kick Volume`에 대응하는 아래쪽 행을 찾습니다. 표의 이름/행 연결이 같은지 확인하고 다음을 지정합니다.

| 아래쪽 표 항목 | 선택할 대상 |
|---|---|
| Device | `VST Mixer` 등 믹서 제어 항목 |
| Channel/Category | 실제 **Kick** 오디오 채널 |
| Value/Action | **Volume** |
| Flags | 연속 값 제어. 별도의 Toggle/버튼 동작을 설정하지 않음 |

**Selected Track / Selected Channel처럼 선택을 따라가는 항목 대신 실제 Kick 채널을 고르는 것이 이 예제의 목적입니다.** 메뉴에 표시된 채널 이름과 MixConsole의 실제 트랙을 맞춰 확인하세요. 선택한 bank가 있다면 설정한 bank가 활성 상태인지도 확인합니다.

**Apply → OK**로 반영합니다. Generic Remote 설정 화면의 Export 기능으로 XML을 별도 파일에 보관합니다. 프로젝트의 트랙 순서/구성을 바꾼 후에는 고정 대상으로 생각한 매핑도 실제 Kick을 움직이는지 다시 확인합니다.

### 4-7. 첫 연결 확인과 dB 캘리브레이션

아직 실측 매핑이 없기 때문에 일반 CubaseMixAI apply로는 테스트할 수 없습니다. **초기 캘리브레이션에만 사용하는 수동 CC 송신**으로 연결을 확인합니다. 다음 명령은 앱의 제안·승인 경로 밖에서 실제 CC를 즉시 보냅니다. 재생을 정지하고 모니터 레벨을 낮춘 테스트 복사본에서 사용자가 직접 실행하며, 일반 믹싱 적용에는 아래 방법 대신 프로그램의 승인 절차를 사용합니다.

MixConsole에서 Kick 페이더가 보이게 하고, 자동화가 값을 되돌리지 않는 테스트 상태에서 실행합니다. 포트 문자열은 `ports` 결과에 맞게 바꾸세요.

```powershell
Set-Location C:\CubaseMixAI
& .\.venv\Scripts\python.exe -c "import mido; p=mido.open_output('CubaseMixAI'); p.send(mido.Message('control_change', channel=0, control=21, value=64)); p.close()"
```

**mido 코드의 `channel=0`은 Cubase 화면/매핑 JSON의 채널 1입니다.** 위 명령의 `control=21`은 CC 주소이며 `value=64`는 전송할 위치입니다.

1. Kick Volume만 움직였는지 확인합니다. 다른 트랙이 움직이면 Generic Remote의 아래쪽 대상을 수정합니다.
2. Kick에 실제로 표시된 dB를 기록합니다. CC64가 몇 dB일지는 미리 가정하지 않습니다.
3. 명령의 `value=64`를 `48`, `80` 등으로 한 번씩 바꿔 실행하고 각 표시 dB를 기록합니다. 값은 0–127 범위입니다.
4. 실제 사용할 dB 주변을 추가로 측정합니다. CC0에서 `-∞`가 나오면 그 점은 보간용으로 사용하지 않습니다.
5. 측정에 쓰지 않은 다른 값도 테스트해 보간 오차를 확인합니다.

| 보낸 CC 값 | Cubase에 표시된 dB |
|---|---|
| 48 | 직접 관측해 기록 |
| 64 | 직접 관측해 기록 |
| 80 | 직접 관측해 기록 |
| 추가 측정값 | 직접 관측해 기록 |

이 수동 명령은 MIDI 출력이나 Cubase 적용 응답을 확인해 주지 않습니다. 실제 화면을 관찰하는 단계입니다. 소리가 바뀌지 않으면 페이더뿐 아니라 mute/solo, 라우팅, 실제 재생 중인 트랙도 확인하세요.

### 4-8. 실측값을 프로그램에 등록

`C:\CubaseMixAI\measurements.local.json`을 UTF-8 BOM 없이 저장합니다. 아래의 `points: []`는 빈 측정 자리이므로 그대로는 생성에 실패합니다. 측정값으로 채워야 합니다.

```json
{
  "port": "CubaseMixAI",
  "controls": {
    "kick.volume": {
      "channel": 1,
      "cc": 21,
      "unit": "dB",
      "max_delta": 3.0,
      "points": []
    }
  }
}
```

`points`는 **`[[Cubase 표시 dB, 보낸 CC 값], ...]`** 순서입니다. 기록표의 열 순서와 반대이므로 주의하세요. 최소 두 점이 필요하고 물리값과 CC가 모두 엄격히 증가해야 합니다.

문법 예시는 `[[-12, 60], [-6, 80], [0, 100]]`이지만 **실측값이 아니므로 그대로 넣지 마세요.** `max_delta: 3.0`은 한 제안에서 움직일 물리값 차이의 최대 3dB를 뜻하며, 실제 보간 가능 범위는 `points`가 결정합니다.

```powershell
& $App calibrate C:\CubaseMixAI\measurements.local.json C:\CubaseMixAI\config\kick-mapping.local.json --confirmed-measured
& $App doctor --mapping C:\CubaseMixAI\config\kick-mapping.local.json
```

생성한 `kick-mapping.local.json`의 `port`, `kick.volume`, channel/cc를 다시 확인합니다. 이미 파일이 있다면 새 이름으로 저장합니다. `calibrate`는 실측값을 등록하는 명령이며 MIDI를 전송하지 않습니다. 확인 옵션이나 `verified: true`만으로 실제 측정이 이루어지지는 않습니다.

독립 관측 결과를 `observations.local.json`으로 기록할 수도 있습니다. 예시 수치는 실제 요청값/관측값으로 교체하세요.

```json
[
  {
    "control": "kick.volume",
    "requested": -2.0,
    "observed": -2.1,
    "tolerance": 0.2
  }
]
```

```powershell
& $App calibration-check C:\CubaseMixAI\config\kick-mapping.local.json C:\CubaseMixAI\observations.local.json
```

`absolute_error`와 `passed`를 확인합니다. 이 명령 자체가 CC를 전송하거나 Cubase에서 값을 읽는 것은 아닙니다.

### 4-9. “킥이 너무 튀어나와, 조금 들어가게 해 줘” 사용 예

먼저 MixConsole에서 **현재 킥 볼륨을 직접 확인**합니다. 이후 WAV와 매핑의 경로를 준비해 Codex에 요청합니다.

```text
cubasemixai MCP를 사용해 줘.
전체 믹스: C:/CubaseMixAI/audio/mix.wav
전체 레퍼런스: C:/CubaseMixAI/audio/reference.wav
킥 스템: C:/CubaseMixAI/audio/kick.wav
킥 매핑: C:/CubaseMixAI/config/kick-mapping.local.json

전체 믹스는 compare, 킥 스템은 analyze로 분석해 줘.
킥이 앞으로 너무 튀어나오는 것이 내 청취 판단이야.
전체 레퍼런스를 킥 단독 레퍼런스로 취급하지 마.
나는 Cubase에서 현재 킥 볼륨이 0dB인 것을 확인했어.
첫 A/B 후보로 kick.volume을 0dB에서 -1dB로 낮추는 pending 제안을
propose 도구로 만들어 줘. 매핑 범위와 max_delta를 지켜 줘.
분석 근거와 한계를 설명하고 apply는 dry_run=true까지만 해 줘.
```

`0dB`는 사용자가 실제 확인한 현재 값으로 바꿉니다. `-1dB` 역시 첫 시험 후보 예시이며 모든 킥에 정답인 값이 아닙니다. 이 예제는 사람이 청취 의도와 첫 후보를 정하고 분석을 검토 근거로 사용하는 방법입니다. 킥 레퍼런스 스템이 따로 있다면 `propose_reference(target=kick)`로 같은 종류의 두 스템을 비교할 수도 있습니다.

UI에서 해당 제안 ID를 확인 → 직접 승인 → 미리보기 → 실제 전송 → MixConsole과 소리 확인 순서로 사용합니다. **매핑을 만드는 것과 매번 변경안을 승인하는 것은 별도**입니다. 상세 적용/복원 절차는 [7장](#approval)을 따릅니다.

<a id="kick-quick-controls"></a>
### 4-10. 킥 컴프레서·EQ를 Track Quick Controls에 연결

볼륨 테스트가 성공한 뒤 확장합니다. 이 경로는 **선택 트랙을 따라가므로 한 트랙씩** 사용합니다. 다음 예제에서는 Kick을 선택한 상태로 유지합니다.

**A. Kick 트랙의 Quick Control 슬롯에 실제 파라미터 할당**

1. Kick 오디오 트랙을 선택합니다.
2. Inspector 또는 Channel Settings의 Inserts에서 사용할 컴프레서를 엽니다. 필요한 EQ도 설정합니다.
3. 프로젝트 창 왼쪽 Inspector에 **Quick Controls** 섹션을 표시합니다. 안 보이면 Inspector 표시/섹션 설정에서 Quick Controls를 켭니다.
4. Quick Control 1의 파라미터 선택 메뉴를 열고 Kick 트랙의 Inserts 아래 해당 컴프레서의 **Threshold**를 선택합니다.
5. Quick Control 2에는 같은 플러그인의 **Ratio**, 3에는 **Attack**, 4에는 **Release**를 지정합니다.
6. Quick Control 5에는 실제 사용할 EQ band의 **Gain**을 지정합니다. EQ 주파수/Q는 먼저 수동으로 정합니다.
7. Inspector의 각 Quick Control을 마우스로 움직여 **원하는 플러그인의 정확한 노브**가 움직이는지 확인하고 원래 값으로 되돌립니다.

플러그인 파라미터는 실제 노출되는 이름으로 선택합니다. 내부 Channel EQ와 insert EQ는 경로가 다를 수 있습니다. 해당 파라미터가 목록에 노출되지 않으면 현재 연결 경로로는 자동 제어하지 않고 수동 조작으로 남깁니다. Quick Control이 표시하는 정규화 수치/백분율과 플러그인의 실제 dB·ms·ratio를 혼동하지 마세요.

**B. 외부 CC를 Track Quick Controls 슬롯에 연결**

1. **Studio → Studio Setup → Track Quick Controls**를 엽니다. **VST Quick Controls**는 별도 장치이므로 이 예제와 혼동하지 않습니다.
2. MIDI Input을 같은 loopMIDI `CubaseMixAI` 포트로 선택합니다.
3. 처음에는 MIDI Output을 Not Connected로 둡니다.
4. 슬롯 1–5의 수신 메시지를 아래 표대로 설정합니다. 각 행의 MIDI Status는 Controller/Control Change, Channel은 1, Max Value는 127, Flags는 Receive/R입니다.
5. Apply/OK로 반영합니다. Generic Remote의 볼륨 CC와 중복되지 않도록 합니다.

| Track Quick Controls 슬롯 | CC 주소 예 | Kick에 할당한 실제 대상 | 프로그램 제어 이름 예 | 물리 단위 |
|---|---|---|---|---|
| 1 | 30 | 컴프레서 Threshold | `kick.compressor.threshold` | dB |
| 2 | 31 | 컴프레서 Ratio | `kick.compressor.ratio` | ratio |
| 3 | 32 | 컴프레서 Attack | `kick.compressor.attack` | ms |
| 4 | 33 | 컴프레서 Release | `kick.compressor.release` | ms |
| 5 | 34 | EQ 저역 band Gain | `kick.eq.bass.gain` | dB |

이는 번호 배정 예시이며 플러그인 제조사가 미리 정해둔 CC가 아닙니다. Quick Control 슬롯이 플러그인 파라미터로 메시지를 전달하므로 플러그인 자체의 MIDI Learn 기능을 사용할 필요는 없습니다.

**C. 실제 수신·단위·캘리브레이션 확인**

Kick을 선택한 상태에서 4-7의 수동 테스트 코드의 `control=21`을 테스트할 주소(예: Threshold는 `control=30`)로 바꾸고, 서로 다른 CC 값을 보내 실제 플러그인의 dB/ratio/ms를 기록합니다. 선택을 바꾸지 말고 각 파라미터를 하나씩 측정한 뒤 초기값을 복원합니다.

매핑 파일에 해당 제어를 추가합니다. 다음 항목은 `controls` 안에 넣는 형식 예시로, 빈 points는 반드시 실측값으로 채워야 합니다.

```json
{
  "kick.compressor.threshold": {
    "channel": 1,
    "cc": 30,
    "unit": "dB",
    "max_delta": 1.0,
    "points": []
  },
  "kick.compressor.ratio": {
    "channel": 1,
    "cc": 31,
    "unit": "ratio",
    "max_delta": 0.2,
    "points": []
  },
  "kick.eq.bass.gain": {
    "channel": 1,
    "cc": 34,
    "unit": "dB",
    "max_delta": 1.0,
    "points": []
  }
}
```

EQ 주파수/Attack/Release 같은 비선형 파라미터는 사용 구간의 측정점을 충분히 기록합니다. 현재 보간기는 엄격히 증가하는 물리값/CC만 지원하므로 역방향·계단형 등 조건에 맞지 않는 제어를 억지로 등록하지 마세요. 모든 측정이 끝나면 새 매핑 파일명으로 `calibrate`를 실행합니다. 입력에 미완료 제어가 있으면 전체 매핑이 거부됩니다.

**D. 여러 스템을 다룰 때의 제한**

- Generic Remote에서 실제 트랙에 연결한 Volume은 서로 다른 CC로 여러 트랙을 제어할 수 있습니다.
- Track Quick Controls의 슬롯 번호/CC는 장치 설정이며 **트랙 선택에 따라 같은 CC의 실제 대상이 바뀝니다.** Kick에서 CC30이 킥 threshold였어도 Vocal을 선택하면 보컬의 슬롯 1을 움직일 수 있습니다.
- 프로그램은 현재 선택된 Cubase 트랙을 읽거나 고정하지 않습니다. `kick.*`라는 이름은 확인을 돕는 이름이며 자동 선택 명령이 아닙니다.
- 선택 의존 QC는 킥용·보컬용 매핑을 분리하고, 해당 트랙을 선택한 한 세션에서만 사용합니다. 같은 채널/CC를 서로 다른 제어로 한 매핑 파일에 중복 등록할 수도 없습니다.
- 제안 생성 후 다른 트랙/플러그인/프리셋을 선택했다면 기존 제안을 그대로 적용하지 말고 대상·현재 값·캘리브레이션을 다시 확인합니다.
- 고정 트랙/플러그인 파라미터가 Generic Remote의 대상 목록에 직접 노출된다면 그 경로를 사용할 수 있지만, 모든 플러그인이 지원한다고 가정하지 않습니다.

따라서 **모든 스템의 Volume 제어**와 **모든 스템의 플러그인 파라미터를 선택과 무관하게 동시 제어**는 같은 기능이 아닙니다. 현재 프로그램에서 선택 의존 QC는 한 트랙씩 검토·승인·적용합니다.

### 4-11. 연결이 안 될 때 확인 순서

| 증상 | 먼저 확인할 곳 |
|---|---|
| `ports`에 포트가 없음 | loopMIDI 실행/포트 생성, 실제 Python 출력 목록 |
| Cubase에서 포트가 없음 | loopMIDI를 먼저 켠 뒤 Cubase 재시작 |
| 아무 페이더도 움직이지 않음 | Generic Remote의 Input, Channel 1, CC21, Receive, Apply, 활성 bank |
| 다른 트랙이 움직임 | 아래 표의 실제 채널 선택, Selected Track 지정 여부, 트랙 순서 변경 |
| 여러 노브가 동시에 움직임 | 같은 CC 중복 수신 장치, QC와 Generic Remote 주소 중복, 피드백 루프 |
| 움직인 값이 바로 되돌아옴 | 해당 트랙/파라미터의 자동화 Read와 기존 automation 데이터 확인. Write는 의도 없이 켜지 않기 |
| Inspector QC는 움직이나 플러그인 노브가 안 움직임 | 슬롯에 할당한 실제 parameter, plugin/bypass와 선택 트랙 |
| 다른 트랙 선택 후 플러그인이 잘못 움직임 | Track Quick Controls의 선택 의존 동작. 원래 대상 트랙과 현재 값 재확인 |
| EQ/컴프레서 값의 단위가 맞지 않음 | QC 정규화 값이 아니라 실제 플러그인 표시값으로 측정했는지 확인 |
| 스템 원본 파일이 바뀌지 않음 | MIDI는 믹서/플러그인을 움직임. 결과 오디오는 Cubase에서 새 WAV로 내보내기 |

연결 후에는 Generic Remote XML, Track Quick Controls 설정, 트랙별 파라미터 할당과 실측 매핑 파일을 함께 보관합니다. XML이나 프로젝트 복사 하나만으로 모든 설정이 복원된다고 가정하지 말고 재실행 후 한 제어부터 다시 확인하세요.

<a id="mcp"></a>
## 5. Codex에 로컬 MCP 서버 등록

### 5-1. 등록 전에 확인

- 프로그램을 설치한 **같은 Windows PC의 PowerShell**에서 실행합니다.
- `C:\CubaseMixAI\.venv\Scripts\cubasemixai-mcp.exe`가 존재해야 합니다.
- CLI/UI와 MCP의 state directory를 `C:\CubaseMixAI\.cubasemixai`로 통일합니다.
- 등록은 한 번만 하면 됩니다. 매일 다시 등록하지 않습니다.

```powershell
Test-Path 'C:\CubaseMixAI\.venv\Scripts\cubasemixai-mcp.exe'
codex --version
```

첫 명령이 `True`여야 합니다. `False`라면 프로젝트 루트에서 가상환경의 Python으로 `-m pip install -e .`를 다시 실행하세요.

### 5-2. MCP 추가 명령

아래는 **한 줄 명령**입니다. 설치 경로가 다르면 두 절대 경로를 함께 바꾸세요.

```powershell
codex mcp add cubasemixai --env 'CUBASEMIXAI_STATE_DIR=C:\CubaseMixAI\.cubasemixai' --env 'OMP_NUM_THREADS=2' -- 'C:\CubaseMixAI\.venv\Scripts\cubasemixai-mcp.exe'
```

이 서버는 **stdio** 방식입니다. `--url http://127.0.0.1:8765`로 등록하지 않습니다. 8765는 승인 UI 주소이고, MCP 서버는 Codex가 필요할 때 별도 프로세스로 시작합니다. 승인 토큰을 `--env`에 넣지 않습니다.

### 5-3. 등록 내용 확인과 실제 연결 확인

```powershell
codex mcp list
codex mcp get cubasemixai
```

`command`가 가상환경의 `cubasemixai-mcp.exe`를 가리키고 환경 변수의 state directory가 UI와 같은지 확인합니다. 이 명령은 **설정 확인**이며 도구가 실제로 동작한다는 검증은 다음 단계에서 합니다.

**PowerShell 창 B**에서 다음을 실행합니다. 창 A의 승인 UI는 계속 실행해 둡니다.

```powershell
Set-Location C:\CubaseMixAI
codex
```

Codex에 아래처럼 요청합니다.

```text
등록된 cubasemixai MCP 서버의 history 도구를 호출해 줘.
다른 도구로 대체하지 말고 MCP 연결 성공 여부와 반환 결과를 알려줘.
아직 제안 생성이나 MIDI 적용은 하지 마.
```

처음 사용한다면 빈 배열 `[]`이 나와도 정상입니다. MCP 연결 오류가 없고 실제 `history` 호출이 성공했는지 확인하세요. 지원하는 Codex 버전에서는 `/mcp`로 연결 상태와 도구 목록도 볼 수 있습니다. 사용 중인 세션이 새 설정을 반영하지 않으면 Codex를 종료하고 다시 실행합니다.

Codex가 도구 사용 권한 확인을 표시하면 요청한 작업의 내용을 보고 판단하세요. Codex의 도구 권한 확인과 CubaseMixAI의 **변경안 승인**은 별개입니다. Codex에서 도구 사용을 허용해도 프로그램의 pending 제안이 자동 승인되지는 않습니다.

### 5-4. 수동 config.toml 설정이 필요한 경우

`codex mcp add`를 사용했다면 보통 필요 없습니다. 시간 제한을 조정하거나 직접 등록하려면 **`$env:USERPROFILE\.codex\config.toml`**의 기존 내용을 보존하면서 아래 서버 항목을 설정합니다. `CODEX_HOME`을 별도로 사용하는 환경이라면 실제 Codex 설정 위치를 따릅니다. 같은 이름의 테이블을 중복 추가하지 마세요.

```toml
[mcp_servers.cubasemixai]
command = 'C:\CubaseMixAI\.venv\Scripts\cubasemixai-mcp.exe'
startup_timeout_sec = 60
tool_timeout_sec = 300

[mcp_servers.cubasemixai.env]
CUBASEMIXAI_STATE_DIR = 'C:\CubaseMixAI\.cubasemixai'
OMP_NUM_THREADS = '2'
```

TOML의 위 경로는 작은따옴표를 사용하므로 역슬래시를 두 번 쓸 필요가 없습니다. Codex를 다시 시작하고 `history` 호출로 확인합니다. 느린 CPU에서 CLAP 호출이 300초를 넘으면 실제 소요 시간에 맞춰 `tool_timeout_sec`를 늘릴 수 있습니다.

### 5-5. 경로가 바뀌었거나 등록을 지우려는 경우

```powershell
codex mcp remove cubasemixai
```

이 명령은 MCP 등록만 제거하며 프로젝트·모델·변경 이력을 삭제하지 않습니다. 다른 폴더로 옮겼다면 새 경로로 5-2의 add 명령을 다시 실행하고 Codex를 재시작합니다.

`cubasemixai-mcp.exe`를 PowerShell에서 직접 실행했는데 화면 출력 없이 기다리는 것은 stdio 요청 대기일 수 있습니다. 일반 사용에서는 직접 켜둘 필요 없이 Codex가 실행하게 두세요. UI 프로세스는 별도로 실행합니다.

<a id="codex-usage"></a>
## 6. Codex와 함께 사용하는 실제 예시

### 6-1. 처음에는 분석만 요청

아래 경로를 내 파일 경로로 바꿔 Codex에 붙여넣습니다.

```text
cubasemixai MCP 도구로 다음 WAV를 분석해 줘.
믹스: C:/CubaseMixAI/audio/mix.wav
레퍼런스: C:/CubaseMixAI/audio/reference.wav
compare를 호출하고 LUFS, peak, 저역/중역/고역, 다이내믹, 스테레오 차이를 설명해 줘.
측정 근거와 불확실성을 구분하고, 아직 변경안 생성이나 MIDI 전송은 하지 마.
```

현재 값과 매핑을 준비하지 않아도 사용할 수 있습니다. 출력 수치는 Codex가 해석하지만 측정 자체는 로컬 프로그램이 수행합니다.

### 6-2. 현재 값 기록

Cubase에서 확인한 현재 파라미터를 `current.local.json`에 저장합니다. **아래 숫자는 예시이며 실제 화면 값으로 바꿉니다.** 실제 등록한 매핑과 현재 값이 모두 있는 제어만 자동 후보가 됩니다.

```json
{
  "master.volume": 0.0,
  "master.eq.bass.gain": 0.0,
  "master.compressor.threshold": -12.0,
  "master.compressor.ratio": 2.0,
  "master.limiter.ceiling": -1.0
}
```

모든 JSON 파일은 UTF-8 BOM 없이 저장하고 경로 문자열 안에서는 `C:/...`처럼 슬래시를 쓰면 JSON 역슬래시 이스케이프 문제를 피할 수 있습니다.

### 6-3. 레퍼런스 기반 변경안 생성

```text
CubaseMixAI의 propose_reference로 마스터 변경안을 만들어 줘.
믹스: C:/CubaseMixAI/audio/mix.wav
레퍼런스: C:/CubaseMixAI/audio/reference.wav
매핑: C:/CubaseMixAI/config/mapping.local.json
target은 master, mode는 master로 해 줘.
현재 값은 C:/CubaseMixAI/current.local.json을 읽어서 객체로 전달해 줘.

MCP의 current_values 인수에는 파일 경로가 아니라 읽은 JSON 객체를 넣어야 해.
state_dir은 서버에 설정된 공용 폴더를 사용하고 따로 바꾸지 마.
생성된 proposal.id, before/after, 변경 이유, 위험, 신뢰도와 skipped 사유를 보여 줘.
apply는 dry_run=true로 미리보기까지만 하고 실제 전송은 하지 마.
```

Codex는 `current.local.json`을 자신의 파일 읽기 기능으로 읽고 MCP에 객체로 전달합니다. 그 파일 읽기 기능이 없는 클라이언트라면 **현재 값 객체 자체를 대화에 붙여넣거나** UI/CLI에서 제안을 생성합니다. MCP의 `propose_reference`가 현재 값 파일을 직접 읽는 것은 아닙니다.

`proposal`이 `null`이면 오류라고 단정하지 마세요. 사용할 매핑/현재 값이 없거나, 변화가 작거나, CC 해상도에서 차이가 없거나, 근거 충돌로 후보가 보류되었을 수 있습니다. `skipped` 사유를 확인합니다.

보컬은 `target=vocal`로 지정하고 보컬 스템을 보컬 레퍼런스 스템과 비교합니다. 전체 믹스를 보컬 스템의 레퍼런스로 사용하지 않습니다. `mode=mix`는 일반 트랙용, `mode=master`는 더 작은 이동 한계와 limiter 검토를 사용하는 모드입니다. 모드를 선택해도 실제 플러그인이 자동 삽입되지는 않습니다.

### 6-4. CLAP 근거도 통합한 변경안

[8장](#clap)의 AI 설치를 완료하고 두 WAV를 각각 30초 이하로 준비한 뒤 요청합니다.

```text
cubasemixai MCP로 DSP와 CLAP을 함께 비교해 줘.
믹스: C:/CubaseMixAI/audio/mix-clip.wav
레퍼런스: C:/CubaseMixAI/audio/reference-clip.wav
CLAP 모델 폴더: C:/CubaseMixAI/.cubasemixai/models/clap
매핑: C:/CubaseMixAI/config/mapping.local.json
현재 값: C:/CubaseMixAI/current.local.json

먼저 clap_compare를 호출해.
그 반환 객체를 요약문으로 바꾸지 말고 propose_reference의 listening 인수에 전달해.
propose_reference에는 같은 두 WAV, target=master, mode=master,
현재 값 파일을 읽은 current_values 객체를 사용해.
DSP와 CLAP이 충돌해 보류된 후보도 설명하고 미리보기까지만 해 줘.
```

`propose_reference` MCP 도구에는 `model_dir` 인수가 없습니다. 위처럼 **`clap_compare` 결과를 `listening`으로 전달**합니다. CLI의 `reference-plan --model-dir ...`는 이 두 작업을 한 번에 수행하는 별도 편의 명령입니다.

### 6-5. 정확한 변경값을 직접 지정

레퍼런스 정책과 별개로, 직접 결정한 값으로 pending 제안을 만들 수도 있습니다.

```text
cubasemixai의 propose 도구로 다음 변경안을 만들어 줘.
mapping_path는 C:/CubaseMixAI/config/mapping.local.json이야.
changes는 [{"control":"vocal.volume","before":0,"after":-2,"unit":"dB"}]야.
reason은 '보컬을 2dB 낮춘 A/B 청취 테스트'로 해 줘.
나는 Cubase에서 현재 값이 0dB인 것을 확인했어.
제안 ID와 dry-run 결과만 보여 주고 실제 전송하지 마.
```

이 숫자도 예시입니다. 실제 현재 값·실측 범위·max_delta에 맞게 바꾸세요. MCP에는 `approve`, `decide`, raw MIDI 송신 도구가 없습니다.

<a id="approval"></a>
## 7. 승인·적용·복원 방법

### 7-1. 브라우저에서 직접 승인·전송

1. 창 A에서 UI를 실행해 두고 브라우저에 해당 실행의 토큰을 입력합니다.
2. **목록 새로고침**으로 Codex가 만든 **정확한 제안 ID**를 찾습니다.
3. 변경 전/후 값, 매핑·대상 트랙, 근거, 위험을 읽습니다.
4. 백업이 있고 현재 Cubase 값이 여전히 `before`와 같음을 확인합니다.
5. 확인 체크박스를 체크하고 **승인**을 누릅니다. 승인만으로는 MIDI가 전송되지 않습니다.
6. **MIDI 미리보기**로 CC를 확인합니다. 미리보기는 전송하지 않습니다.
7. **승인된 변경 실제 전송**을 누르고 화면의 확인에 답합니다.
8. Cubase 페이더/파라미터의 실제 변화와 소리를 확인합니다.

Codex와 UI가 같은 폴더를 사용해야 같은 제안이 보입니다. 제안은 **생성 시점부터 15분** 동안 유효하고 승인해도 유효 시간이 연장되지 않습니다. 실제 전송은 제안당 한 번만 시도합니다.

### 7-2. 승인 후 Codex에게 적용을 요청하는 방법

브라우저에서 직접 승인한 뒤, UI 전송 버튼을 누르는 대신 Codex에게 요청할 수 있습니다. **UI와 Codex 중 한쪽에서만 실제 적용합니다.**

```text
제안 ID <여기에 실제 proposal.id>를 로컬 UI에서 직접 승인했어.
Cubase의 현재 값과 프로젝트 백업도 확인했어.
cubasemixai apply 도구를 proposal_id=<위 ID>, dry_run=false로 한 번만 호출해 줘.
전송 실패나 uncertain/sending 상태면 자동으로 재시도하지 말고 상태를 알려줘.
```

`<...>` 부분을 실제 ID로 교체합니다. UI에서 이미 전송했다면 다시 요청하지 않습니다. 도구가 성공해도 반환의 `acknowledged_by_cubase`는 `false`이며, 이는 Cubase 적용 응답을 받는 구조가 아니라는 뜻입니다.

### 7-3. 거절·복원·실패 처리

- 미적용 pending 제안은 **거절**할 수 있습니다. 매핑이나 값이 틀렸다면 수정 후 새 제안을 생성합니다.
- 적용 결과가 마음에 들지 않으면 UI의 **복원 변경안 생성 (재승인 필요)**를 사용합니다. 복원은 즉시 전송하지 않고 반대 방향의 pending 제안을 만듭니다.
- 복원 제안의 `before`가 현재 Cubase 값과 같은지 확인한 뒤 다시 승인·적용합니다.
- `uncertain` 또는 `sending`은 일부 CC만 적용됐을 가능성이 있습니다. 실제 값을 확인해 정확한 현재 값으로 새 제안을 만듭니다. 역방향 제안을 확인 없이 적용하지 않습니다.

Codex 복원 요청 예:

```text
제안 ID <실제 ID>의 history 상태를 확인하고 restore 도구로 복원 제안만 만들어 줘.
원래 값과 되돌릴 값을 보여 주고 실제 전송하지 마.
부분 전송 가능성이 있으면 내가 현재 값을 확인하도록 알려줘.
```

| 상태 | 의미와 다음 행동 |
|---|---|
| `pending` | 아직 승인 전. 검토 후 승인 또는 거절 |
| `approved` | 사용자 승인 완료. 유효 시간 안에 한 번 적용 가능 |
| `rejected` | 거절됨. 적용 불가 |
| `sending` | 전송 시도 시작 기록. 계속 남아 있으면 현재 값 확인 |
| `sent` | 기존 CC 경로의 Python 전송 완료. Cubase 화면·청취로 별도 확인 |
| `verified` | 새 DirectAccess 경로의 목표 파라미터/UID를 fresh read로 확인. 음질 개선 확인과는 별개 |
| `uncertain` | 실패/부분 전송 가능성. 자동 재시도하지 않기 |

### 7-4. CLI만으로 제안·미리보기·적용

승인은 브라우저에서 하고, 나머지는 PowerShell에서도 실행할 수 있습니다. 아래 명령은 2-3의 `$App`과 state 환경 변수를 지정한 창에서 실행합니다.

```powershell
& $App reference-plan C:\CubaseMixAI\audio\mix.wav C:\CubaseMixAI\audio\reference.wav C:\CubaseMixAI\config\mapping.local.json C:\CubaseMixAI\current.local.json --mode master
& $App history
```

반환받은 ID를 지정합니다.

```powershell
$ProposalId = '실제 제안 ID로 교체'
& $App apply $ProposalId
```

브라우저에서 승인한 뒤에만 실제 적용할 수 있습니다.

```powershell
& $App apply $ProposalId --live
```

복원 제안 생성 명령은 다음과 같습니다. 생성 후 다시 브라우저에서 검토·승인합니다.

```powershell
& $App restore $ProposalId
```

<a id="clap"></a>
## 8. CLAP AI 청취 설치와 사용

### 8-1. 한 번만 설치

UI/Codex를 종료한 상태에서 별도 PowerShell 창을 열고 설치합니다.

```powershell
Set-Location C:\CubaseMixAI
& .\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
& .\.venv\Scripts\python.exe -m pip install -e '.[ai]'
& .\.venv\Scripts\cubasemixai.exe setup-ai C:\CubaseMixAI\.cubasemixai\models\clap
```

공식 `laion/clap-htsat-unfused` 모델을 내려받고 revision과 SHA-256을 기록합니다. 모델은 약 590MB이고 PyTorch 및 설치·변환 과정에 추가 공간이 필요합니다. 인터넷 연결이 필요하며 CPU에서도 실행됩니다. `setup-ai`는 새 빈 모델 폴더를 요구하므로 이미 설치한 폴더에 반복 실행하지 않습니다. 실패 후 부분 파일이 남았다면 새 이름의 빈 폴더를 사용하고 그 경로를 이후 명령에도 반영하세요.

공식 PyTorch 가중치는 torch 2.6+의 `weights_only=True`로 로드한 뒤 safetensors로 저장합니다. 추론 시 모델을 자동 다운로드하지 않습니다. 설치 후 UI와 Codex를 다시 실행합니다.

### 8-2. 실제 실행 확인

```powershell
$App = 'C:\CubaseMixAI\.venv\Scripts\cubasemixai.exe'
$env:OMP_NUM_THREADS = '2'
& $App listen C:\CubaseMixAI\audio\mix-clip.wav C:\CubaseMixAI\audio\reference-clip.wav C:\CubaseMixAI\.cubasemixai\models\clap
```

임베딩 유사도, `brightness/punch/space`, 프롬프트 margin 차이, window spread, 불확실성이 표시됩니다. 30초를 넘는 파일은 Cubase에서 대응 구간을 짧게 내보내세요.

- 최대 10초씩 시작·중간·끝 window를 결정적으로 선택하고 레벨을 정규화합니다.
- stereo는 에너지가 더 큰 채널을 분석합니다. 스테레오 폭은 DSP 지표로 확인합니다.
- 프롬프트 친화도와 코사인 유사도는 품질 점수나 보정된 확률이 아닙니다.
- DSP와 CLAP 근거가 충돌하면 관련 EQ/컴프레서 후보를 사람의 청취 검토로 넘깁니다.

CLI에서 CLAP을 포함한 변경안을 한 번에 생성하려면:

```powershell
& $App reference-plan C:\CubaseMixAI\audio\mix-clip.wav C:\CubaseMixAI\audio\reference-clip.wav C:\CubaseMixAI\config\mapping.local.json C:\CubaseMixAI\current.local.json --mode master --model-dir C:\CubaseMixAI\.cubasemixai\models\clap
```

실제 모델 smoke test를 다시 실행하려면 프로젝트 루트에서 다음을 사용합니다. 합성 음원으로 모델 실행 경로를 확인하며 실제 곡의 청취 품질을 검증하는 테스트는 아닙니다.

```powershell
& .\.venv\Scripts\python.exe scripts\validate_ai.py C:\CubaseMixAI\.cubasemixai\models\clap
```

<a id="sections"></a>
## 9. 스템·후렴·드롭 분석

### 9-1. 스템 분석

킥·808·보컬·기타를 Cubase에서 각각 WAV로 내보냅니다. 이 프로그램이 전체 믹스에서 스템을 자동 분리하지는 않습니다. `stems.local.json` 예:

```json
{
  "kick": "C:/CubaseMixAI/audio/kick.wav",
  "808": "C:/CubaseMixAI/audio/808.wav",
  "vocal": "C:/CubaseMixAI/audio/vocal.wav",
  "guitar": "C:/CubaseMixAI/audio/guitar.wav"
}
```

```powershell
& $App stems C:\CubaseMixAI\stems.local.json
```

Codex에서는 파일을 읽어 `analyze_stems`의 `stems` 인수에 경로 객체를 전달하도록 요청합니다. 네 가지 이름 중 실제 준비한 스템만 넣으면 됩니다.

### 9-2. 후렴·드롭 구간 비교

서로 같은 음악적 역할의 구간을 선택합니다. 두 곡의 후렴이 시작하는 시간이 같을 필요는 없습니다. `sections.local.json` 예:

```json
[
  {"name":"chorus","start":30,"end":50,"reference_start":40,"reference_end":60},
  {"name":"drop","start":65,"end":80,"reference_start":70,"reference_end":85}
]
```

```powershell
& $App sections C:\CubaseMixAI\audio\mix.wav C:\CubaseMixAI\audio\reference.wav C:\CubaseMixAI\sections.local.json
```

Codex 요청 예:

```text
cubasemixai compare_sections로 구간을 비교해 줘.
믹스는 C:/CubaseMixAI/audio/mix.wav,
레퍼런스는 C:/CubaseMixAI/audio/reference.wav야.
sections는 [{"name":"chorus","start":30,"end":50,"reference_start":40,"reference_end":60}]를 사용해.
후렴의 저역, 보컬이 있는 중역, peak와 다이내믹 차이를 설명해 줘.
전체 믹스 통계만으로 특정 악기 원인이라고 단정하지 마.
```

시간은 예시이므로 실제 곡 길이와 구간에 맞게 바꿉니다. CLAP까지 해당 구간을 비교하려면 각 구간을 별도의 30초 이하 WAV로 내보냅니다.

<a id="mastering"></a>
## 10. 백업·마스터링·재렌더·A/B 청취

### 10-1. 프로젝트 백업과 복원

먼저 Cubase의 Back up Project로 폴더 밖 미디어를 모은 뒤 저장·종료합니다. 아래 source 폴더에는 루트에 `.cpr`이 있어야 합니다.

```powershell
& $App backup C:\Projects\TestMix C:\Backups\TestMix-001
& $App verify-backup C:\Backups\TestMix-001
& $App restore-project C:\Backups\TestMix-001 C:\Restored\TestMix-001
```

백업·복원 대상은 기존 폴더가 아닌 새 폴더여야 합니다. 파일 SHA-256을 검증하며 symlink/junction과 변경 중인 소스는 거부합니다. 폴더 밖 미디어와 Cubase의 저장하지 않은 상태는 복사하지 못합니다. 복원한 프로젝트를 Cubase에서 직접 열어 미디어 누락이 없는지 확인하세요.

프로젝트 백업과 MIDI 복원 제안은 다릅니다. 프로젝트 백업은 디스크 파일을 보존하고, MIDI 복원 제안은 기록된 파라미터 입력값으로 돌아가기 위한 새 제안입니다.

### 10-2. 마스터 체인 준비

Cubase 마스터 버스에 **EQ → compressor → true-peak limiter**를 직접 삽입하고 bypass·순서·oversampling·ceiling 단위를 확인합니다. 실제 접근 가능한 Quick Controls를 실측 매핑에 등록합니다.

```powershell
& $App master-chain C:\CubaseMixAI\config\mapping.local.json
```

`mapped`, `manual_or_unmapped`를 보고 실제 설정이 필요한 항목을 확인합니다. 이 명령이 플러그인을 삽입하거나 체인의 실제 상태를 읽는 것은 아닙니다. `reference-plan --mode master`로 제안한 변경은 7장의 승인 절차를 거쳐 적용합니다.

### 10-3. 재렌더 작업 만들기

변경 전 WAV를 덮어쓰지 말고 `before.wav`로 보존합니다. 실제 적용 후 다음 작업을 준비합니다.

```powershell
& $App render-start C:\CubaseMixAI\audio\before.wav C:\CubaseMixAI\audio\reference.wav C:\CubaseMixAI\exports\after-001.wav
```

반환의 `id`는 **재렌더 작업 ID**입니다. 변경안의 `proposal.id`와는 다른 ID입니다. 출력 경로는 아직 존재하지 않는 새 WAV여야 합니다.

Cubase에서 같은 locator·sample rate·channel 수로 Audio Mixdown을 실행해 안내된 경로에 저장합니다. 이 프로그램이 Cubase의 내보내기 버튼을 누르지는 않습니다. 내보내기가 완전히 끝난 후:

```powershell
$JobId = '실제 재렌더 작업 ID로 교체'
& $App render-finish $JobId
```

CLAP으로도 재청취하려면 before/after/reference가 모두 30초 이하인 작업을 준비하고 다음을 사용합니다.

```powershell
& $App render-finish $JobId --model-dir C:\CubaseMixAI\.cubasemixai\models\clap
```

한 작업은 한 번 완료 처리합니다. 완료된 작업을 다시 가져오거나 다른 옵션으로 비교하려면 새 작업/새 출력 파일을 사용하거나 아래 독립 `evaluate` 명령을 사용하세요.

```powershell
& $App evaluate C:\CubaseMixAI\audio\before.wav C:\CubaseMixAI\exports\after-001.wav C:\CubaseMixAI\audio\reference.wav
```

Codex 요청 예:

```text
cubasemixai evaluate_render로 전후를 비교해 줘.
before: C:/CubaseMixAI/audio/before.wav
after: C:/CubaseMixAI/exports/after-001.wav
reference: C:/CubaseMixAI/audio/reference.wav
지표별로 좋아진 점과 나빠진 점을 설명하되 수치만으로 최종 개선이라고 단정하지 마.
```

AI 재비교까지 요청한다면 `clap_compare(before, reference)`와 `clap_compare(after, reference)`를 각각 호출한 결과를 `evaluate_render`의 `listening_before`, `listening_after`에 전달하도록 합니다. CLI에서는 `evaluate ... --model-dir ...`가 이를 묶어서 수행합니다.

### 10-4. 레벨을 맞춘 A/B 파일

```powershell
& $App ab C:\CubaseMixAI\audio\before.wav C:\CubaseMixAI\exports\after-001.wav C:\CubaseMixAI\exports\ab-001
```

새 폴더에 `A.wav`, `B.wav`, `manifest.json`이 생성됩니다. 같은 목표 LUFS와 공통 peak 여유를 적용한 FLOAT WAV이며 EQ·압축·리미팅을 새로 추가하지 않습니다. 최종 납품 마스터로 사용하지 않고 청취 비교에 사용합니다.

Cubase에 두 파일을 가져와 같은 재생 경로에서 번갈아 들어보세요. 전후 파일의 길이·샘플레이트·채널 수가 같아야 하고, 도구는 같은 locator로 정렬됐는지까지 자동 판별하지 않으므로 직접 확인합니다. 보컬 명료도, 킥/808 충돌, 펀치, 저역, 위상, 피로감과 clipping을 확인합니다.

### 10-5. JSON·HTML 보고서 저장

UI의 **결과 JSON 저장**으로 받은 파일을 사용하면 간단합니다. CLI 출력에서 저장할 때는 Windows PowerShell 버전에 따라 `>`가 UTF-16을 만들 수 있으므로 명시적으로 UTF-8 BOM 없이 저장합니다.

```powershell
$Report = & $App compare C:\CubaseMixAI\audio\mix.wav C:\CubaseMixAI\audio\reference.wav
$Utf8 = [System.Text.UTF8Encoding]::new($false)
[System.IO.File]::WriteAllText('C:\CubaseMixAI\exports\analysis-001.json', ($Report -join "`n"), $Utf8)
& $App report C:\CubaseMixAI\exports\analysis-001.json C:\CubaseMixAI\exports\report-001.html
```

HTML은 독립 파일이므로 브라우저에서 열어 볼 수 있습니다. 기존 HTML을 덮어쓰지 않으므로 다른 파일명으로 저장하세요. Codex에서는 분석 반환 객체를 `export_report`의 `report`에, 새 HTML 경로를 `output`에 전달해 저장하도록 요청할 수 있습니다.

<a id="daily"></a>
## 11. 매일 사용하는 순서와 업데이트

### 매일 시작할 때

1. loopMIDI를 켜고 `CubaseMixAI` 포트가 있는지 확인합니다.
2. Cubase에서 테스트 복사본을 열고 백업·매핑·현재 값을 확인합니다.
3. PowerShell 창 A에서 2-3의 경로 변수를 지정하고 `& $App --state-dir $State ui`를 실행합니다.
4. 브라우저에 이번 실행의 토큰을 직접 입력합니다.
5. 창 B에서 프로젝트 폴더로 이동해 `codex`를 실행합니다. MCP 등록은 이미 되어 있으므로 다시 add하지 않습니다.
6. WAV 분석 → 변경안 → 직접 승인 → 한 번 적용 → 새 WAV → 전후 비교 순서로 사용합니다.
7. 종료 시 UI 창에서 `Ctrl+C`, Codex와 Cubase를 정상 종료합니다. 프로젝트를 저장했는지 확인합니다.

### 업데이트할 때

UI와 Codex 세션을 종료한 뒤 실행합니다. 직접 수정한 추적 파일이 있다면 먼저 자신의 변경을 보관하세요.

```powershell
Set-Location C:\CubaseMixAI
git status
git pull --ff-only
& .\.venv\Scripts\python.exe -m pip install -e .
```

AI 의존성도 갱신할 때는 마지막 명령에 `-e '.[ai]'`를 사용합니다. 모델을 다시 받을 필요는 없으며 의도적으로 모델을 교체할 때 새 빈 폴더에 설치합니다. 업데이트 후 UI와 Codex를 다시 실행합니다. 설치 경로가 같으면 MCP 재등록은 보통 필요 없습니다.

`.cubasemixai`를 삭제하면 로컬 이력과 모델이 사라질 수 있습니다. `.local.json` 매핑/현재 값과 상태 폴더는 Git에 자동 업로드되지 않으므로 별도로 보관하세요.

<a id="troubleshooting"></a>
## 12. 오류 해결

| 증상 | 확인과 해결 |
|---|---|
| `py -3.11`을 찾을 수 없음 | Python 3.11 x64와 launcher 설치 확인. 다른 지원 버전을 쓸 경우 venv 생성 명령을 해당 버전으로 변경 |
| `npm`/`codex`를 찾을 수 없음 | Node LTS 설치 후 PowerShell 새 창. npm 전역 설치 경로가 PATH에 있는지 확인 |
| `npm.ps1`/`codex.ps1` 실행 정책 오류 | `npm.cmd`/`codex.cmd` 사용. 가상환경은 activate 없이 exe 경로로 실행 |
| `cubasemixai-mcp.exe`가 없음 | 프로젝트 루트에서 가상환경 Python의 `-m pip install -e .` 실행 |
| MCP가 등록됐지만 도구 호출 실패 | `codex mcp get cubasemixai`의 command·절대 경로 확인, Codex 재시작, `history` 실제 호출 |
| MCP 서버를 8765 URL로 등록함 | 해당 등록을 remove하고 stdio `command` 방식으로 다시 add. 8765는 승인 UI 전용 |
| Codex에는 제안이 있는데 UI 목록이 비어 있음 | 토큰을 입력하고 목록 새로고침. MCP env와 UI의 `State directory`가 동일한지 확인 |
| UI가 403을 반환함 | `http://127.0.0.1:8765`로 열고 이번 실행의 토큰 입력. 임의 도메인/원격 프록시로 열지 않기 |
| 8765 포트 사용 중 | 기존 UI가 이미 실행 중인지 확인. 이전 UI를 정상 종료한 뒤 실행 |
| `MIDI output not found` 또는 출력 목록이 비어 있음 | loopMIDI 실행·포트 이름 확인. Cubase가 아닌 Python의 출력 목록부터 확인 |
| `Calibration is not verified` | 예시 파일 대신 모든 제어의 실측점으로 만든 매핑 사용. 일부 제어만 미검증이어도 전체 매핑이 거부됨 |
| `Value outside calibrated range` / 변화량 초과 | 현재/목표 값의 단위, points 범위, max_delta 확인. 범위를 추측해 넓히지 말고 추가 측정 |
| `Simulation mapping cannot send live MIDI` | 시뮬레이션 매핑의 의도된 차단. 실기기용으로 실제 측정한 별도 매핑 준비 |
| `Mapping changed` / `Source WAV changed` | 제안 후 매핑/근거 파일이 바뀜. 기존 제안을 재사용하지 않고 새 분석·제안 생성 |
| `unexpired` / 만료 오류 | 생성 후 15분 경과 또는 미승인/이미 적용된 ID인지 확인. 현재 값을 다시 확인해 새 제안 생성 |
| `proposal: null` | `skipped` 확인. 매핑·현재 값 누락, 작은 변화, CC 해상도 또는 근거 충돌 보류일 수 있음 |
| JSON 시작 문자/BOM 오류 | 파일을 UTF-8 BOM 없이 저장. JSON 경로는 `C:/...` 또는 이스케이프한 역슬래시 사용 |
| CLAP import 또는 모델 파일 오류 | 같은 `.venv`에 `.[ai]` 설치 여부, setup-ai 성공, 모델 폴더 경로 확인 |
| CLAP 파일 길이 초과 | mix/reference와 재렌더 비교의 before/after를 각각 30초 이하로 내보내기 |
| CLAP MCP timeout | 짧은 clip과 CPU 스레드 설정 확인. Codex config의 `tool_timeout_sec`를 실제 실행 시간에 맞춰 조정 |
| 재렌더가 길이/형식 불일치로 거부됨 | 동일 locator/sample rate/channels로 다시 내보내기. 새 export 경로 사용 |
| 출력 폴더/보고서가 이미 존재함 | 백업·복원·A/B·HTML은 새 경로/이름 사용. 원본을 덮어쓰지 않음 |
| `uncertain` / `sending` | 부분 적용 가능. 자동 재시도하지 말고 Cubase 값을 직접 확인해 새 제안 작성 |

<a id="reference"></a>
## 13. 파일·상태·MCP 도구 목록과 검증 범위

### 주요 파일

| 경로 | 내용 |
|---|---|
| `config/mapping.example.json` | 설명용 예시. 실제 캘리브레이션 아님 |
| `config/mapping.local.json` | 사용자가 측정한 실제 CC·단위·보간점 |
| `current.local.json` | 사용자가 Cubase에서 확인한 현재 값 |
| `.cubasemixai/history.sqlite3` | 변경안·승인 상태·적용 이력 |
| `.cubasemixai/<id>.before.json` | 적용 전 **사용자 입력값** 스냅샷. 실제 DAW readback이나 프로젝트 백업 아님 |
| `.cubasemixai/renders/` | 재렌더 작업·평가 기록 |
| `.cubasemixai/models/clap/` | 로컬 CLAP 모델·revision·해시 |

WAV 분석과 CLAP 추론은 로컬에서 수행하며 이 MCP 구현이 WAV 파일 자체를 외부로 업로드하지는 않습니다. Codex로 도구를 호출하면 반환되는 분석 수치·경로·요약은 Codex 대화의 문맥으로 전달될 수 있습니다. 로컬 토큰은 같은 사용자 권한의 악의적 프로그램에 대한 보안 경계가 아닙니다.

### MCP 도구 29개

| 작업 | 도구 |
|---|---|
| Cubase 15 조회 | `remote_status`, `remote_tracks`, `remote_inspect`, `remote_plugins` |
| Cubase 15 제안 | `remote_propose`, `remote_propose_plugin` |
| MIDI 표현 파일 생성 | `add_midi_expression` |
| WAV/DSP | `analyze`, `compare`, `analyze_stems`, `compare_sections` |
| 판단·AI | `recommend`, `integrate`, `clap_compare`, `propose_reference` |
| 변경안·이력 | `propose`, `apply`, `history`, `restore` |
| 프로젝트 보존 | `backup_project`, `verify_backup`, `restore_project` |
| 캘리브레이션·체인 | `calibration_report`, `master_chain` |
| 재렌더·보고서 | `create_render_job`, `finish_render_job`, `evaluate_render`, `export_ab`, `export_report` |

모든 경로는 **MCP 서버가 실행되는 Windows PC의 로컬 경로**입니다. `propose_reference.current_values`나 `analyze_stems.stems`처럼 객체를 요구하는 인수에는 파일 경로 문자열 대신 객체를 전달합니다. `apply`의 기본 `dry_run`은 `true`이고, 승인 API는 MCP에 노출하지 않습니다.

### 검증 범위와 개발 테스트

0.2의 자동 테스트·실제 CPU CLAP·브라우저·Windows/Linux CI를 확인했고, 0.3에서는 DirectAccess driver mock·양방향 프로토콜·실제 상태 기반 승인 테스트를 추가했습니다. 최신 결과는 검증 기록을 참고하세요. 실제 사용자 음원의 청취 판단, Cubase Generic Remote/QC 실기기, 원본 프로젝트 복원과 최종 마스터링은 사용자 환경에서 확인해야 합니다.

[남은 설정·검증 체크리스트](docs/verification-checklist.md) · [단계별 구현 범위](docs/roadmap.md) · [검증 기록](docs/validation.md) · [검증 환경 버전](docs/environment-tested.json)

개발 테스트:

```powershell
Set-Location C:\CubaseMixAI
& .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
& .\.venv\Scripts\python.exe -m pytest -q
```

실제 브라우저 smoke test는 먼저 8765 포트의 UI를 종료한 뒤 실행합니다. 임시 음원과 시뮬레이션 매핑을 사용하며 실기기에 MIDI를 보내지 않습니다.

```powershell
& .\.venv\Scripts\python.exe -m pip install -e '.[browser]'
& .\.venv\Scripts\python.exe -m playwright install chromium
& .\.venv\Scripts\python.exe scripts\validate_browser.py
```

GitHub Actions는 기본 Windows/Linux 테스트와 Linux 브라우저 검증을 실행합니다. Actions의 **Run workflow**로 수동 실행하면 공식 모델을 설치하는 AI smoke job도 실행합니다. `requirements-tested.txt`는 초기 Linux 환경의 버전 기록이며 Windows용 범용 잠금 파일이 아닙니다.
