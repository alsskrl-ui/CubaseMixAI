# CubaseMixAI + Cubase Complete MCP

두 프로그램을 같이 쓰면 CubaseMixAI는 WAV 분석·CLAP·보수적 믹스 제안·표현 MIDI 파일 생성을 맡고, Cubase Complete MCP는 Cubase 15의 프로젝트와 transport, 트랙, 플러그인, MIDI import/export, WAV 렌더를 제어합니다. 두 프로그램은 별도의 로컬 MCP 서버이며 Codex가 둘 다 등록해 연결합니다.

## 기능을 나눠 쓰기

| 하고 싶은 일 | 사용할 MCP |
|---|---|
| 레퍼런스/믹스 WAV의 LUFS·주파수·다이내믹·스테레오 비교, 선택 CLAP 평가 | `cubasemixai` |
| 선택 트랙을 같은 양만큼 낮추기, 대응 스템 기반 fader 제안, 렌더 피크 -6 dBFS 목표 제안 | `cubasemixai` |
| 트랙·transport 제어, Cubase에서 트랙 만들기/이름 변경, 실제 mixer 값 확인 | `cubase-complete` |
| 설치 플러그인 catalog 확인, 빈 슬롯에 플러그인 삽입, 지원 파라미터 제어 | `cubase-complete` |
| MIDI 문서 작곡·Cubase import·export, 프로젝트 저장/열기, Cubase WAV 렌더 | `cubase-complete` |
| 자연어로 만든 애프터터치·CC1·피치벤드 파일을 가져와 소리 확인 | `cubasemixai`로 파일 생성 후 `cubase-complete`로 import |

각 프로젝트가 주장하는 검증 범위는 다릅니다. Cubase Complete MCP의 upstream capability matrix는 Cubase 15.0.30 fixture에서 15개 live acceptance cases를 통과했다고 보고합니다. CubaseMixAI와 함께 두 MIDI Remote driver를 동시에 띄운 조합은 이 프로젝트에서 검증하지 않았습니다. 처음에는 백업한 테스트 프로젝트에서 각각 `cubasemixai remote_status`와 `cubase_status`를 확인하고 작은 읽기 작업부터 하세요.

## Windows 설치와 Codex 등록

CubaseMixAI의 Python 설치와 `cubasemixai` MCP 등록은 기존 [Windows/Codex 매뉴얼](windows-codex-manual.md)을 먼저 완료합니다. 다음으로 upstream의 [v1.0.0 Windows release](https://github.com/muhwagwa0112/cubase-complete-mcp/releases/tag/v1.0.0)를 별도 폴더에 내려받아 압축을 풀고 release 안내에 있는 SHA-256으로 검증합니다. 이 소스에 포함된 release asset의 해시는 `22ef05d1daddfa04a7e4bbfa7b0c822170a8c4b531cd2cf7d77635cf4b6b4df7`입니다. .NET 8 Desktop Runtime과 Cubase 15가 필요합니다.

loopMIDI에서 두 서버용 포트를 각각 만듭니다. 이름이 정확히 달라야 합니다.

| 서버 | Cubase 방향 | 컴퓨터 방향 |
|---|---|---|
| CubaseMixAI | `CubaseMixAI To Cubase` | `CubaseMixAI From Cubase` |
| Cubase Complete MCP | `CubaseMCP To Cubase` | `CubaseMCP From Cubase` |

Cubase를 닫고 release 폴더에서 upstream 안내대로 드라이버를 설치합니다.

```powershell
Set-Location C:\Tools\CubaseCompleteMcp
.\CubaseCompleteMcp.Cli.exe backup pre-setup
.\CubaseCompleteMcp.Cli.exe setup
```

Cubase를 다시 열어 프로젝트를 띄운 뒤 Codex에 두 번째 MCP 서버를 등록합니다. 경로는 실제 압축 해제 위치로 바꿉니다.

```powershell
codex mcp add cubase-complete -- 'C:\Tools\CubaseCompleteMcp\CubaseCompleteMcp.Server.exe'
codex mcp list
```

기존 `cubasemixai` 등록을 지우거나 교체하지 않습니다. Codex를 재시작한 뒤 아래처럼 서버별 상태를 확인합니다.

```text
cubasemixai MCP에서 remote_status를 호출하고, cubase-complete MCP에서 cubase_status를 호출해.
두 서버의 연결 상태와 Cubase API 기능을 각각 보여줘. 아무것도 변경하지 마.
```

## 함께 쓰는 예

```text
reference.wav와 CubaseMixAI에서 export한 mix.wav를 cubasemixai MCP로 비교해.
저역과 전체 음량 차이를 설명해줘. 그다음 cubase-complete MCP로 트랙 목록과
Kick/Bass의 현재 Volume을 확인해. 레퍼런스가 stereo 한 파일뿐이므로 스템별 정답을 추정하지 말고,
내가 확인할 수 있도록 후보와 근거만 설명해. 아무 변경도 하지 마.
```

```text
source.mid에서 애프터터치와 ±6 cents 피치 흔들림을 넣은 새 MIDI를
cubasemixai MCP로 만들어줘. 원본은 보존해.
결과 파일을 cubase-complete MCP의 cubase_midi import 기능으로 새 트랙에 가져와.
Cubase에서 가져온 결과와 트랙명을 다시 확인해줘.
```

```text
cubase-complete MCP로 현재 프로젝트를 저장하고 locator 구간을 WAV로 export해.
export가 완료되면 cubasemixai MCP로 export.wav의 LUFS, peak, 주파수와
reference.wav의 차이를 분석해줘. 피크가 -6 dBFS에서 벗어나면 Stereo Out 변경안만 만들고
실제 적용은 로컬 승인 UI를 기다려.
```

Cubase Complete MCP의 `cubase_batch`는 여러 Cubase 작업을 한 승인 묶음으로 계획하며 실패 시 완료된 작업을 자동 반복하지 않습니다. `cubasemixai`의 동일량 fader batch는 선택 목록의 채널 Volume을 모두 같은 dB만큼 낮춥니다. 둘의 batch는 별도 도구와 상태 기록을 사용합니다.

## 범위와 주의

- upstream Cubase Complete MCP는 Windows 전용이고 Cubase 15가 필요합니다. plugin catalog와 할당은 upstream 문서상 MIDI Remote API 1.3인 Cubase 15.0.30 이상에서 지원됩니다.
- CubaseMixAI의 분석 결과를 Cubase Complete MCP에 자동으로 넘겨 믹싱 결정을 적용하는 단일 알고리즘은 없습니다. Codex가 두 서버를 차례로 호출하고 사용자가 제안 내용을 검토합니다.
- 레퍼런스 WAV에서 보컬·킥·베이스 스템을 자동 분리하는 기능은 어느 쪽에도 포함하지 않았습니다.
- `.cpr` 내부 바이너리는 직접 수정하지 않습니다. Cubase Complete MCP는 Cubase UI를 통해 프로젝트 작업과 렌더를 수행합니다.
- upstream 소스는 [MIT License](../integrations/CubaseCompleteMcp/LICENSE)이며, 포함 위치·원본 commit·release 해시는 [UPSTREAM.md](../integrations/CubaseCompleteMcp/UPSTREAM.md)에 기록했습니다.
