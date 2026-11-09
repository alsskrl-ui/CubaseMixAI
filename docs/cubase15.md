# Cubase 15: MIDI Remote DirectAccess 사용 가이드

CubaseMixAI 0.4에서는 기존 CC 외에 **MIDI Remote DirectAccess**와 별도 MIDI 표현 파일 생성을 제공합니다. 지원되는 트랙/플러그인 파라미터는 수동 CC 매핑 없이 실제 호스트 값을 읽고, 대상을 식별해 승인 후 변경합니다. [API 조사 근거](cubase15-api-research.md)

실제 Cubase 15에서의 드라이버 로드·대상/값·플러그인 지원은 아직 사용자 환경에서 검증해야 합니다. 처음에는 작업 복사본에서 킥 볼륨 하나로 확인하세요. 기존 DSP/CLAP·백업·MCP 등록은 README 절차를 그대로 사용합니다.

## 빠른 요약

Cubase 15에서는 MIDI Remote API가 노출한 믹서 객체를 읽고, 승인된 파라미터 변경을 적용한 다음 실제 값을 다시 읽을 수 있습니다. API 1.3 plugin manager가 있으면 설치 플러그인 목록 조회와 빈 Insert 슬롯 삽입도 가능합니다.

| 요청 예시 | 프로그램이 하는 일 |
|---|---|
| “트랙 목록과 Kick의 Volume 현재값만 보여줘.” | 트랙 identity와 실제 호스트 값을 읽음 |
| “킥이 너무 앞에 있어. 1 dB 낮추는 안을 만들어. 아직 적용하지 마.” | 실제 단위가 dB인지 확인한 뒤 pending 변경안을 만듦 |
| “이 빈 Insert 슬롯에 내가 고른 플러그인을 넣는 안을 만들어.” | 지원 API에서 catalog 확인 후 빈 슬롯 대상 제안을 만듦 |
| “믹스와 레퍼런스 WAV 차이를 분석해줘.” | Cubase에서 내보낸 파일을 DSP/선택적 CLAP으로 분석 |

**사용 흐름:** 두 loopMIDI 포트 생성 → MIDI Remote 드라이버 설치·로드 → `remote-status` 확인 → Codex MCP에서 조회·제안 → 로컬 UI에서 직접 승인 → 적용·값 재확인 → Cubase에서 새 WAV를 내보내 청취.

현재 제어 범위는 호스트가 실제로 노출한 트랙/파라미터이며, 플러그인 삽입은 지원 API가 있고 슬롯이 비어 있을 때만 가능합니다. WAV 자동 렌더링, 기존 플러그인 교체·삭제, 최종 음질 판단은 수동입니다. `verified`는 Cubase 값 확인을 뜻하며 소리의 개선을 뜻하지 않습니다. 아래 절은 설치와 각 단계의 세부 절차입니다.

## 1. 업데이트와 두 MIDI 포트

UI와 Codex를 종료하고 설치 폴더에서 업데이트합니다.

```powershell
Set-Location C:\CubaseMixAI
git pull --ff-only
& .\.venv\Scripts\python.exe -m pip install -e .
$App = 'C:\CubaseMixAI\.venv\Scripts\cubasemixai.exe'
$State = 'C:\CubaseMixAI\.cubasemixai'
$env:CUBASEMIXAI_STATE_DIR = $State
```

loopMIDI에서 이름이 정확히 다음인 **두 포트**를 만듭니다.

| 포트 | Cubase 입장 | Python 입장 |
|---|---|---|
| `CubaseMixAI To Cubase` | MIDI Input | MIDI Output: 요청 전송 |
| `CubaseMixAI From Cubase` | MIDI Output | MIDI Input: 실제 결과 수신 |

같은 포트를 양쪽에 쓰지 않습니다. 기존 `CubaseMixAI` CC 포트와 별개입니다. 처음 설치할 때 기존 Generic Remote와 새 driver로 같은 대상을 동시에 조작하지 마세요.

## 2. Cubase 15 드라이버 파일 설치

Steinberg 공식 [Getting Started](https://steinbergmedia.github.io/midiremote_api_doc/getting-started/)의 Driver Scripts 구조를 사용합니다.

1. Cubase 15를 한 번 실행하고 프로젝트 창 아래 MIDI Remote 탭을 열어 기본 폴더를 생성합니다.
2. 실제 사용자 문서 폴더의 `Steinberg\Cubase\MIDI Remote\Driver Scripts` 위치를 확인합니다. OneDrive 등으로 문서가 이동했다면 실제 위치를 사용합니다.
3. Cubase를 종료한 뒤 아래 명령으로 그 **Driver Scripts 폴더**에 원본 CubaseMixAI driver를 내보냅니다.

```powershell
& $App remote-setup 'C:\Users\내사용자명\Documents\Steinberg\Cubase\MIDI Remote\Driver Scripts'
```

`내사용자명`과 전체 경로를 실제 값으로 바꿉니다. 다음 파일이 생성됩니다.

```text
Driver Scripts/Local/CubaseMixAI/DirectBridge/CubaseMixAI_DirectBridge.js
C:/CubaseMixAI/.cubasemixai/remote.json
```

명령은 기존 driver/config를 덮어쓰지 않습니다. 재설치·업데이트 시 기존 파일을 먼저 별도 보관하고 경로를 확인하세요. 프로그램 설치 경로와 Cubase의 Driver Scripts 경로는 서로 다릅니다.

4. loopMIDI를 켠 상태에서 Cubase 15를 시작하고 테스트 프로젝트를 엽니다.
5. MIDI Remote의 Script Console/관리 화면에서 필요하면 **Reload Scripts**를 실행합니다.
6. `CubaseMixAI / DirectBridge` 장치가 로드되고 Input=`To Cubase`, Output=`From Cubase`로 연결되는지 확인합니다. 표면을 수동으로 만들며 CC를 하나씩 등록하는 방식이 아니라 JS driver를 로드하는 방식입니다.
7. 이 두 입력이 연주용 All MIDI Inputs에 섞이지 않는지도 확인합니다.

자동 감지가 안 되면 우선 파일 위치·파일명, 실제 MIDI 포트 이름, Script Console 오류를 확인합니다. 버전/에디션별 관리 화면은 다를 수 있습니다. 로딩 성공은 다음 host handshake로 확인합니다.

## 3. Python 포트 이름과 실제 연결 확인

```powershell
& $App ports
& $App remote-status
```

첫 명령은 MIDI **출력** 목록입니다. 입력 목록은 다음 명령으로도 확인합니다.

```powershell
& .\.venv\Scripts\python.exe -c "import mido; print(mido.get_input_names())"
```

Windows MIDI 백엔드가 이름 뒤에 숫자 접미사를 붙인다면 `.cubasemixai/remote.json`의 Python 쪽 이름을 정확히 수정합니다.

```json
{
  "output_port": "CubaseMixAI To Cubase",
  "input_port": "CubaseMixAI From Cubase",
  "timeout": 15
}
```

Cubase의 detection 이름은 위 기본 loopMIDI 이름이고, JSON은 Python이 실제로 보는 포트 문자열입니다. timeout 범위는 1–60초입니다. 다른 config 위치를 쓰려면 CLI/UI와 Codex MCP에 같은 `CUBASEMIXAI_REMOTE_CONFIG` 절대 경로를 설정합니다. 기본값은 공용 state directory의 `remote.json`이므로 보통 추가 환경 변수는 필요 없습니다.

성공한 `remote-status`는 `driver: CubaseMixAI/1`, `host_version`, `session`, 다음 capabilities를 반환합니다.

- `direct_access`: 트랙/객체 조회와 normalized 값 제어 가능 여부
- `physical_conversion`: 호스트 물리값 ↔ normalized 변환 가능 여부
- `plugin_manager`: plugin catalog/slot assignment 가능 여부

없는 기능을 강제로 활성화하지 않습니다. API 1.2 host에서는 DirectAccess 일부를 사용할 수 있어도 물리값/플러그인 관리가 거부될 수 있습니다. API 1.3 plugin 기능은 공개 참고 프로젝트의 15.0.30 사례가 있으나, 정확한 사용 가능 여부는 자신의 `remote-status`와 실제 catalog 호출로 확인합니다.

## 4. Codex MCP 등록과 첫 조회

기존 `cubasemixai` MCP 등록을 그대로 사용할 수 있습니다. Python 패키지를 업데이트하고 Codex를 재시작하면 **29개 도구**가 조회되어야 합니다. 기본 등록:

```powershell
codex mcp add cubasemixai --env 'CUBASEMIXAI_STATE_DIR=C:\CubaseMixAI\.cubasemixai' --env 'OMP_NUM_THREADS=2' -- 'C:\CubaseMixAI\.venv\Scripts\cubasemixai-mcp.exe'
```

이미 등록되어 있다면 중복 add 대신 `codex mcp get cubasemixai`로 경로를 확인합니다. UI는 별도 창에서 `& $App --state-dir $State ui`로 실행합니다.

Codex 요청:

```text
cubasemixai MCP의 remote_status와 remote_tracks를 호출해 줘.
실제 API capabilities와 트랙 목록을 보여줘. 아직 어떤 값도 바꾸지 마.
Kick 트랙은 이름만으로 추측하지 말고 호스트가 반환한 session,
object_id, unique_id, unique_name, title이 포함된 target 객체를 사용해.
같은 이름의 트랙이 여러 개라면 내가 대상을 고를 수 있게 보여줘.
```

`remote_tracks`의 각 track 객체 자체가 target입니다. target은 프로젝트/driver 세션에 묶여 있으므로 문서의 예시 ID를 복사하거나 다른 세션에서 재사용하지 않습니다. 트랙 순서는 주소가 아니라는 점도 기존 CC 경로와 다릅니다.

## 5. 킥 파라미터 찾기와 1dB 후보

Codex 요청:

```text
방금 확인한 Kick target으로 remote_inspect를 호출해 줘.
Kick 채널과 필요한 자식 객체를 차례로 조회해서 실제 Volume 파라미터를 찾아줘.
object_id, parameter tag, normalized, display, plain, unit을 보여줘.
태그나 단위를 추측하지 말고, 조회 결과에 없으면 없다고 말해.
현재 값은 사용자가 입력한 예시가 아니라 실제 readback을 사용해.
```

`remote_inspect`는 객체당 파라미터 64개를 반환합니다. `next_offset`이 있으면 `parameter_offset`을 지정해 계속 조회합니다. `children`의 객체 ID를 같은 target과 함께 전달해 Inserts·플러그인·EQ·Panner 등을 탐색합니다. 다른 트랙의 자식 객체를 같은 target에 섞으면 거부됩니다.

다음 요청은 **Volume의 실제 unit이 `dB`이고 plain 변환이 가능함을 확인한 뒤** 사용합니다.

```text
내 청취로는 킥이 너무 앞으로 나와. 첫 A/B 후보로 킥을 1dB 낮춰 보자.
실제 Kick Volume 조회값의 plain에서 1을 뺀 목표값으로
remote_propose를 호출해 줘. value_kind=plain, unit은 호스트가 반환한 dB,
max_delta=1.0으로 해 줘. target/object_id/parameter_tag는 방금 실제 조회한 것을 사용해.
reason에는 킥 전진감 완화를 위한 첫 A/B 후보라는 점과 분석 근거를 적어줘.
제안 ID와 실제 before, 목표값, 대상 identity를 보여주고 apply는 dry_run=true까지만 해.
```

host plain 단위가 선형 amplitude이거나 `dB`가 아니라면 dB처럼 더하고 빼지 않습니다. 자동 변환이 확인되지 않는 경우 명시적인 normalized 목표값을 사용하거나 수동으로 검토합니다. normalized delta 한계는 최대 0.25, plain delta 한계는 최대 3이며, 기본 `max_delta=0.1`은 단위에 맞게 사용자가 더 작게 제한할 수 있습니다.

기존 `propose_reference`는 CC 매핑용 DSP 휴리스틱입니다. 새 경로에서 분석과 제안을 연결하려면 **분석 → 실제 호스트 파라미터 조회 → remote_propose** 순서로 요청합니다. 기존 매핑을 자동 변환하거나 근거 없이 host tag를 만들어 쓰지 않습니다.

## 6. 승인·적용·호스트 확인

1. 기존 로컬 UI에 토큰을 입력하고 제안 목록을 새로고침합니다.
2. `backend: midi_remote`, 실제 target·object·before·after·이유를 확인합니다.
3. 백업과 대상 상태를 확인하고 직접 승인합니다.
4. MIDI 미리보기 후 **승인된 변경 실제 전송**을 한 번 실행하거나, Codex에 같은 ID의 `apply(dry_run=false)`를 한 번만 요청합니다.
5. 프로그램은 승인 시와 실제 dispatch callback에서 현재 값·대상·파라미터를 다시 비교합니다. 검사와 쓰기는 같은 JS callback에서 순서대로 수행하지만 Cubase 프로젝트 전체의 원자적 transaction을 제공하는 것은 아닙니다.
6. 적용 후 별도 호스트 readback이 목표 normalized 값과 일치할 때만 `verified` 상태로 저장합니다.

`acknowledged_by_cubase: true` / `verification: fresh_direct_access_read`는 이 경로의 파라미터/객체 후조건을 확인했다는 뜻입니다. 오디오 품질 개선까지 확인한 것은 아닙니다. automation이 나중에 값을 덮어쓸 수도 있으므로 재생 중 값과 청취를 확인하세요.

다른 트랙을 선택하더라도 mixer target identity로 주소를 지정합니다. 반면 프로젝트 전환, 대상 삭제·교체·이름 변경, plugin 교체, 승인 전후의 값 변경은 거부 사유가 됩니다. 세션이 바뀌면 `remote_tracks`부터 다시 조회합니다. 전송 후 응답 유실/결과 불일치는 `uncertain`이며 자동 재전송하지 않습니다. 한 driver 세션의 mutation request 한도는 512개이고 대규모 객체/파라미터 탐색에는 한계가 있어 초과 시 명시적으로 거부합니다. 세션을 다시 활성화한 후에는 target과 제안을 새로 조회해야 합니다.

파라미터 복원은 기존 `restore`로 **실제 현재 값을 새로 읽은 역방향 pending 제안**을 만듭니다. 다시 승인해야 하며 이전 세션/대상 변경 시에는 새 조회가 필요합니다.

## 7. 플러그인 목록과 빈 슬롯 삽입

API 1.3 `plugin_manager`가 있을 때만 사용합니다.

1. `remote_inspect`로 대상 track → Inserts → **실제 빈 slot object**를 찾습니다.
2. `remote_plugins(target, slot_id)`로 그 슬롯에 사용할 수 있는 설치 catalog를 조회합니다. `next_offset`이 있으면 `offset`으로 계속 조회합니다.
3. 사용자가 선택한 **catalog의 UID**로 `remote_propose_plugin` pending 제안을 만듭니다.
4. 로컬 UI에서 직접 승인한 뒤 기존 `apply`를 한 번 실행합니다.
5. 삽입 후 slot의 실제 child unique name이 선택한 class UID를 나타내는지 확인해야 `verified`가 됩니다.

Codex 요청 예:

```text
Kick target의 Inserts 아래 빈 슬롯을 조회하고 remote_plugins로 실제 설치 목록을 보여줘.
아직 삽입하지 마. 내가 사용할 플러그인을 고르면 목록에 있는 UID로
remote_propose_plugin을 호출해 pending 제안만 만들어줘.
기존 플러그인이 들어 있는 슬롯은 교체하지 마.
```

현재 삽입 경로는 32자리 hex UID를 가진 catalog 플러그인, 빈 슬롯만 지원합니다. 이름으로 UID를 만들어 내지 않습니다. 기존 플러그인 교체·삭제, preset 불러오기, plugin 삽입의 자동 복원은 지원하지 않습니다. 새 플러그인의 기본값도 곡에 맞는 설정이라고 가정하지 말고 삽입 후 실제 파라미터를 다시 조회합니다.

## 8. 실제 검증 목록과 한계

- [ ] Cubase 15의 정확한 build·edition과 API capabilities 기록
- [ ] driver 로드, 양방향 두 포트 handshake, 29개 MCP 도구 조회
- [ ] Kick/Vocal을 따로 만들고 Vocal이 선택된 상태에서 Kick Volume만 바뀌는지 확인
- [ ] 킥 트랙 재정렬 후 동일 identity를 따라가는지 확인
- [ ] 대상 삭제·plugin 교체·프로젝트 전환·값 수동 변경 시 기존 제안을 거부하는지 확인
- [ ] 실제 dB/ratio/ms 단위와 plain conversion roundtrip을 화면과 비교
- [ ] 적용 후 host readback·automation 재생·청취 확인
- [ ] catalog 목록, 빈 슬롯 plugin 삽입, 실제 UID 확인
- [ ] 포트 단절/응답 유실 시 uncertain으로 남고 자동 재시도하지 않는지 확인
- [ ] 새 WAV를 내보내 DSP/CLAP·레벨 매칭 청취로 개선 여부 확인

WAV export와 전체 프로젝트 저장·GUI 대화상자는 이번 backend에서 자동 실행하지 않습니다. readback은 노출된 host 상태를 확인하는 것이며 최종 믹스 청취를 대체하지 않습니다. 이 드라이버의 테스트는 Node API-shaped fake host이며 Cubase runtime을 재현했다고 주장하지 않습니다.

<a id="midi-expression"></a>
## MIDI 클립에 피치벤드·모듈레이션·애프터터치 추가

이 기능은 Cubase Remote API를 통해 즉시 연주 이벤트를 보내는 기능이 아닙니다. 악기 트랙에서 내보낸 단일 MIDI 클립을 입력해, 표현 이벤트가 추가된 **새 `.mid` 파일**을 만들고 Cubase에서 직접 가져옵니다. WAV는 이미 렌더된 오디오라 pitch bend나 aftertouch를 넣을 수 없습니다. 원본을 덮어쓰지 않으며 이미 pitch bend/CC1/channel aftertouch가 있는 대상 채널은 중복 적용을 막기 위해 거부합니다.

Codex MCP 예시:

```text
source.mid를 expressive.mid로 복사하면서 피치가 천천히 불안하게 움직이도록 해줘.
피치 흔들림은 최대 6 cents, pitch bend range는 악기 설정과 같은 2 semitones로 해.
원본은 보존하고 결과 파일 경로와 사용한 범위를 알려줘. 모듈레이션과 aftertouch는 추가하지 마.
```

기본값으로 실행하는 같은 CLI 명령:

```powershell
cubasemixai midi-expression source.mid expressive.mid --pitch-wander-cents 6 --pitch-bend-range-semitones 2
```

변조와 채널 애프터터치를 더하려면 깊이를 0–127 범위로 지정합니다. 예를 들어:

```powershell
cubasemixai midi-expression source.mid expressive.mid --pitch-wander-cents 6 --pitch-bend-range-semitones 2 --modulation-depth 24 --aftertouch-depth 16 --rate-hz 8
```

작업 순서는 **악기 파트 MIDI 내보내기 → 새 파일 생성 → Cubase에 가져오기 → 같은 악기/채널로 라우팅 → 기존 파트와 비교 청취**입니다. 먼저 복사본 프로젝트에서 확인하세요. 6 cents는 기본으로 생성되는 최대 피치 변화량이며, pitch-bend range 값은 악기에서 실제 설정한 semitone 범위와 일치해야 합니다. 잘못 설정하면 흔들림 크기가 예상과 달라집니다. 모듈레이션(CC1)과 channel aftertouch는 신스와 프리셋이 지원해야 소리가 달라집니다. pitch bend와 channel aftertouch는 같은 MIDI 채널에서 동시에 울리는 음에 모두 작용합니다. 기존 파트에 덮어쓰거나 MIDI를 Cubase 프로젝트에 자동 배치하지 않습니다.
