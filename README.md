# CubaseMixAI 0.4

레퍼런스 WAV를 분석하고, Cubase 현재 상태를 API로 읽어 믹스 변경안을 제안하며, MIDI 표현이 들어간 새 파일을 만드는 로컬 도구입니다. 기본은 로컬 승인 UI에서 검토하는 방식이고, 사용자가 Auto 모드를 명시적으로 켠 동안에만 새 제안을 자동 승인·적용합니다.

## Cubase 15 기능 확장 통합

Cubase 제어 기능을 보강하기 위해 MIT 라이선스의 [Cubase Complete MCP](https://github.com/muhwagwa0112/cubase-complete-mcp)를 소스와 라이선스 그대로 `integrations/CubaseCompleteMcp/`에 포함했습니다. 이 프로젝트는 Cubase 15.0.30에서 실제 검증했다고 보고한 제어·프로젝트 작업 서버이며, CubaseMixAI의 오디오 분석·CLAP·믹싱 판단 기능을 대체하지 않습니다. 두 MCP 서버를 Codex에 등록해 함께 사용합니다.

| CubaseMixAI MCP | Cubase Complete MCP |
|---|---|
| 레퍼런스/믹스 WAV의 LUFS·주파수·다이내믹 분석, CLAP 보조 청취 | Cubase transport, 트랙 목록·생성·이름 변경, 믹서 제어 |
| 동일량 트랙 페이더 batch, 스템 비교 제안, 렌더 피크 목표 제안 | 검증된 batch workflow, 플러그인 catalog/빈 슬롯 할당, MIDI Remote 세부 조회 |
| 애프터터치·CC1·피치벤드 MIDI 파일 생성 | MIDI 작곡 문서 생성과 Cubase import, 프로젝트 저장·열기, WAV export |

두 서버는 각자 별도 loopMIDI 포트를 사용합니다. CubaseMixAI는 `CubaseMixAI To Cubase` / `CubaseMixAI From Cubase`, 확장 서버는 `CubaseMCP To Cubase` / `CubaseMCP From Cubase` 포트를 만듭니다. 자세한 설치와 병행 사용은 [통합 가이드](docs/cubase-integration.md)를 참고하세요. 확장 서버는 Windows와 .NET 8이 필요하며 플러그인 목록/삽입은 Cubase 15.0.30 이상에서 지원됩니다.

## Codex에서 할 수 있는 일: 필요한 것과 예시

레퍼런스는 **완성된 스테레오 WAV 한 파일**이면 전체 믹스 분석에 충분합니다. 이 파일과 내 믹스 WAV를 비교해 LUFS, peak, 주파수 대역, 다이내믹, 스테레오 차이를 확인할 수 있습니다. 다만 한 개의 완성 믹스만으로 킥·베이스·보컬 각각의 원래 레벨이나 페이더 값을 분리해 알아낼 수는 없습니다. 현재 프로그램에는 스템 분리 기능이 없습니다.

### 1. 레퍼런스와 내 믹스 비교

**준비:** 레퍼런스 `reference.wav` 한 개와 Cubase에서 렌더한 `mix.wav`. CLAP은 선택 사항이며 없어도 DSP 측정은 됩니다. 이 작업에는 loopMIDI가 필요 없습니다.

```text
reference.wav는 완성 믹스 레퍼런스고 mix.wav는 내 믹스야.
두 파일의 후렴을 비교해 음량, 저역, 다이내믹, 스테레오 차이를 설명해줘.
CLAP이 설치되어 있으면 “펀치감”과 “밝기” 비교도 덧붙여줘.
아직 Cubase 값은 바꾸지 말고 측정 근거와 한계를 먼저 보여줘.
```

### 2. Cubase 트랙 페이더를 레퍼런스에 맞춰 조정

**준비:** Cubase 15 DirectAccess 연결과 loopMIDI 포트 2개, Codex MCP 등록, 로컬 승인 UI. 일괄 페이더 제안에는 각 대상 트랙의 현재 WAV와 **같은 역할로 준비된 레퍼런스 스템 WAV**가 한 쌍씩 필요하고, Cubase에서 읽은 실제 트랙 identity와 Volume parameter tag도 필요합니다. 전체 레퍼런스 WAV만 있는 경우에는 전체 믹스 차이 설명과 수동 검토용 변경 제안까지만 할 수 있습니다. 스테레오 레퍼런스로부터 프로그램이 킥/스네어/보컬 스템을 만들어내지는 않습니다.

```text
reference.wav는 전체 레퍼런스야. 이 파일과 mix.wav를 먼저 분석해 차이를 설명해줘.
현재 레퍼런스에는 분리 스템이 없으니 트랙별 수치를 추정하지 마.
Cubase의 Kick, Bass, Vocal Volume을 조회하고, 가능한 안전한 조정 후보만 설명해줘.
Cubase 변경은 만들거나 적용하지 마.
```

트랙별 대응 스템을 이미 준비한 경우에만, `remote_propose_reference_volumes`로 한 번에 최대 32쌍의 변경안을 만들 수 있습니다. 적용은 한 번의 로컬 승인 뒤 순차 진행되며, 먼저 복사본 프로젝트에서 확인하세요.

레퍼런스 없이 선택한 트랙 페이더를 모두 같은 양만큼 낮추는 `remote_propose_lower_all_faders`도 있습니다. `remote_tracks`와 `remote_inspect`에서 확인한 각 트랙의 실제 Volume 정보를 목록으로 넘기고, 예를 들어 2 dB 낮추기를 지정하면 각 페이더를 현재 값에서 정확히 2 dB씩 낮추는 단일 승인 묶음을 만듭니다. 마스터 출력은 별도 단계로 측정해야 하므로 목록에서 제외합니다. 이 기능은 전체 출력 피크를 -6 dBFS로 맞춘다고 보장하지 않습니다.

```text
Cubase에서 믹서 트랙과 각 트랙의 실제 Volume parameter tag를 조회해줘.
Stereo Out은 제외하고 나머지 오디오 트랙 페이더를 각각 2 dB씩 낮추는
remote_propose_lower_all_faders 제안만 만들어. 실제 적용은 하지 마.
```

### 3. 마스터 출력 피크를 -6 dBFS 목표로 조정

**준비:** Cubase 연결·loopMIDI·MCP·승인 UI와 Cubase에서 새로 렌더한 스테레오 마스터 WAV. 이는 트랙별 레퍼런스 스템을 요구하지 않습니다. 측정된 출력 sample peak를 기준으로 Stereo Out 페이더 변경안을 별도로 만들고, 적용 후 다시 렌더해 확인합니다. 마스터 페이더를 -6 dB 위치에 놓는다는 뜻은 아닙니다.

```text
reference.wav는 전체 레퍼런스 믹스야. 먼저 mix.wav와 비교해줘.
Cubase Stereo Out의 실제 Volume을 조회하고, 방금 렌더한 master.wav의
sample peak를 측정해 -6 dBFS 목표 변경안을 제안해줘. 최대 1 dB만 움직이고
적용하지 마. 로컬 승인 화면에 제안이 생기면 거기서 확인할게.
```

### 4. MIDI에 애프터터치·모듈레이션·피치 흔들림 추가

**준비:** WAV가 아니라 MIDI 파일과 사용할 악기/프리셋. 이 도구는 새 MIDI 파일을 만들며 Cubase로 가져와 들어봐야 합니다. 파일 생성만 할 때는 loopMIDI가 필요 없습니다. CC1/애프터터치는 악기가 지원해야 소리가 바뀌고, 피치벤드 범위는 악기 설정과 일치해야 합니다.

```text
source.mid를 원본 보존한 채 expressive.mid로 복사해.
채널 애프터터치는 처음 0, 중간에 80까지 올리고 끝에서 0으로 내려줘.
피치벤드는 중심 주위로 불안하게 ±6 cents 흔들리게 해줘.
이벤트가 들어간 새 파일을 만들고 경로를 알려줘. Cubase에 직접 기록했다고 말하지 마.
```

### 5. 플러그인 확인·삽입·파라미터 변경

**준비:** Cubase 15 DirectAccess, loopMIDI 두 포트, MCP 및 로컬 승인 UI. 먼저 API에서 보이는 플러그인/Insert/파라미터를 조회합니다. 지원되는 경우 빈 슬롯 플러그인 삽입과 노출된 파라미터 변경을 승인 제안으로 만들 수 있습니다. API에 안 보이는 플러그인 값은 제어할 수 없습니다.

```text
Cubase에서 Vocal 트랙의 Insert와 사용 가능한 플러그인을 조회해줘.
아직 삽입하거나 값을 바꾸지 말고, 컴프레서를 빈 슬롯에 추가할 수 있는지와
노출된 threshold/ratio 파라미터를 보고해줘.
```

### CLAP과 loopMIDI는 언제 필요한가?

- **CLAP:** 선택 기능. 주관적 설명(밝음, 펀치감, 공간감)과 WAV의 유사도를 보조 비교합니다. 설치는 `python -m pip install -e ".[ai]"` 후 매뉴얼의 모델 준비 단계를 따릅니다. CLAP은 자동 스템 분리나 EQ 정답, 사람의 최종 청취를 대신하지 않습니다.
- **loopMIDI:** Cubase 15 DirectAccess에서 Codex가 Cubase 상태를 조회하고 승인된 파라미터 변경을 전달할 때 필요합니다. 문서에 안내된 입력·출력 가상 포트를 만들고 Cubase를 재시작합니다. WAV 분석, CLAP 비교, MIDI 파일 새로 만들기 자체에는 필요하지 않습니다.
- **로컬 승인 UI:** 기본 변경 검토·승인과 선택적 Auto 모드에 필요합니다. Codex 대화만으로 승인 경계를 우회하지 않으며, Auto 적용은 UI에서 사용자가 직접 켠 동안에만 동작합니다.

### 준비된 분석 파일을 읽고 현재 세션에 맞춰 작업하기

WAV와 분석 JSON을 한 작업 폴더에 두면 `remote_agent_context`가 `reference.wav`, `mix.wav`, `analysis/*.json`, 동일한 파일명이 있는 `stems/mix/`와 `stems/reference/`를 찾아 읽고 Cubase API에서 현재 트랙·Volume 값도 함께 조회합니다. 폴더 예시는 [`config/agent-session.example.json`](config/agent-session.example.json)과 아래 요청을 참고하세요. 파일을 짝짓는 스템명과 Cubase 고유 트랙 ID는 사용자가 manifest에서 연결해야 하며 이름만으로 위험한 쓰기를 하지 않습니다.

```text
remote_agent_context를 C:/CubaseMixAI/session 폴더로 실행해.
읽힌 분석 JSON, mix/reference WAV 차이, 각 스템 비교, Cubase 트랙 identity와
현재 페이더를 바탕으로 조정 후보를 설명해줘. 레퍼런스 스템이 없으면 개별 악기의
레벨을 추정하지 마. 먼저 remote_batch_volume으로 최대 1 dB씩 변경 제안을 만들고,
플러그인이 필요하면 remote_find_insert와 remote_map_insert로 실제 설치·파라미터를 확인해.
적용 전에 제안 근거와 위험을 알려줘.
```

`remote_batch_volume`은 출력 채널을 제외한 전체 채널 또는 선택된 `unique_id`에 동일한 dB 변화를 제안합니다. `remote_channel_fader`와 `remote_map_insert`는 현재 호스트 값을 읽고, `remote_find_insert`는 설치된 플러그인을 검색해 빈 슬롯 삽입 제안을 만듭니다. Codex는 읽기→분석→제안→적용→다시 읽기의 여러 MCP 호출을 에이전트처럼 이어갈 수 있습니다. UI의 **Auto 켜기**는 켜져 있는 동안 모든 MCP에서 새로 생성되는 제안을 자동 적용하므로 요청과 제안 내용을 확인하며 사용하고, 필요하지 않을 때 끄세요.

피치벤드와 채널 애프터터치는 같은 MIDI 채널의 동시에 울리는 음에 함께 작용합니다. CLAP 가이드는 [상세 매뉴얼](docs/windows-codex-manual.md#clap), Cubase와 MCP 연결은 [Windows/Codex 매뉴얼](docs/windows-codex-manual.md)을 참고하세요.

## 시작하기

Cubase 15 DirectAccess 연결, Python 가상환경, loopMIDI, Codex 로컬 MCP 등록은 [상세 Windows/Codex 매뉴얼](docs/windows-codex-manual.md)을 참고하세요. Cubase 15 드라이버 설치와 기능 한계는 [Cubase 15 가이드](docs/cubase15.md)에 있습니다.

```powershell
git clone https://github.com/alsskrl-ui/CubaseMixAI.git C:\CubaseMixAI
Set-Location C:\CubaseMixAI
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e .
```

CLAP 청취가 필요하면 `-e '.[ai]'`로 설치합니다. MIDI 표현 파일 생성은 다음 CLI로도 실행할 수 있습니다.

```powershell
cubasemixai midi-expression source.mid expressive.mid --pitch-wander-cents 6 --pitch-bend-range-semitones 2
```

## 확인이 필요한 점

Cubase 15 DirectAccess는 fake host·프로토콜·프로그램 테스트를 통과했지만 실제 Cubase 15 설치에서 아직 검증하지 않았습니다. Cubase API가 노출하지 않는 트랙·플러그인·파라미터는 제어할 수 없습니다. 마스터링 판단과 최종 청취는 사용자가 직접 해야 합니다.

- [Cubase 15 API 조사](docs/cubase15-api-research.md)
- [구현 단계와 남은 작업](docs/roadmap.md)
- [검증 기록](docs/validation.md)
