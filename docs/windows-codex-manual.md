# Windows + Cubase + Codex 빠른 가이드

Cubase가 설치된 Windows PC 기준입니다. 스마트폰의 ChatGPT GitHub 연결과 로컬 Cubase MCP 등록은 서로 다른 설정입니다.

## 1. 설치

Python 3.11 x64, Git, Node.js LTS, Codex CLI, Cubase를 설치합니다. loopMIDI는 Cubase 15 MIDI Remote 연결에 필요합니다.

```powershell
git clone https://github.com/alsskrl-ui/CubaseMixAI.git C:\CubaseMixAI
cd C:\CubaseMixAI
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\cubasemixai.exe doctor
```

CLAP 청취가 필요하면 `python -m pip install -e ".[ai]"`를 실행합니다. WAV DSP 분석에는 CLAP이 필요하지 않습니다.

## 2. Cubase 연결

처음에는 Cubase에서 테스트 프로젝트 복사본을 백업해 사용합니다.

- **Cubase 15:** [DirectAccess 설치·API 가이드](cubase15.md)를 따릅니다. loopMIDI에 `CubaseMixAI To Cubase`와 `CubaseMixAI From Cubase` 포트를 만들고 드라이버 연결을 확인합니다.
- **Cubase 10.5:** [Generic Remote 가이드](windows-cubase.md)를 따릅니다. 파라미터별 CC와 dB 대응값은 실제 측정값으로 등록해야 합니다.

필요한 조작·플러그인 값이 Cubase API에서 노출되지 않으면 해당 조작은 자동 제어할 수 없습니다. 두 MCP를 같이 쓸 때는 [통합 가이드](cubase-integration.md)를 참고하세요.

## 3. Codex에 MCP 등록

프로젝트 루트의 PowerShell에서 등록합니다. 서버는 stdio 프로세스이므로 UI 주소(8765)를 MCP URL로 등록하지 않습니다.

```powershell
codex mcp add cubasemixai --env 'CUBASEMIXAI_STATE_DIR=C:\CubaseMixAI\.cubasemixai' -- 'C:\CubaseMixAI\.venv\Scripts\cubasemixai-mcp.exe'
codex mcp get cubasemixai
codex mcp list
```

Codex를 다시 시작한 후 다음처럼 실제 도구 호출을 확인합니다.

```text
cubasemixai MCP의 history를 호출하고 연결 결과를 알려줘.
```

설정 제거는 `codex mcp remove cubasemixai`입니다. 프로젝트를 이동한 경우 새 절대 경로로 다시 등록합니다.

## 4. 분석 자료와 세션 설정

예시 구조:

```text
session/
  reference.wav
  mix.wav
  analysis/*.json
  stems/mix/*.wav
  stems/reference/*.wav
  cubasemixai-session.json
```

manifest 예시는 [agent-session.example.json](../config/agent-session.example.json)입니다. 파일 경로, stem pair, Cubase `unique_id` 매핑을 실제 값에 맞게 지정하세요. 파일명만으로 트랙을 추측하지 않습니다. MCP의 `remote_agent_context`가 자료와 현재 Cubase 트랙/페이더를 읽습니다.

```text
remote_agent_context로 C:/CubaseMixAI/session을 읽어줘.
분석 JSON과 WAV 비교, 명시된 스템 매핑, Cubase 트랙/페이더를 요약해.
근거가 있는 제안만 최대 1 dB 변화로 만들고 적용은 하지 마.
```

전체 레퍼런스 WAV 하나로는 킥·보컬 등 개별 트랙 레벨을 분리할 수 없습니다. 역할별 비교에는 대응하는 레퍼런스 스템이 필요합니다.

## 5. 사용 예시

**전체 믹스 비교**

```text
reference.wav와 mix.wav의 LUFS, peak, 저역, 다이내믹, 스테레오 차이를 요약해.
아직 Cubase를 바꾸지 말고 측정 근거와 불확실성을 알려줘.
```

**선택 트랙 일괄 감쇄**

```text
현재 Cubase Volume 값을 조회해 Stereo Out을 제외한 지정 트랙을 각각 2 dB 낮추는
제안만 만들어. 적용은 하지 마.
```

**마스터 피크 목표**

```text
새로 렌더한 master.wav의 sample peak를 분석하고 Stereo Out을 -6 dBFS peak 목표로
조정하는 안을 제안해. 페이더 변경은 최대 1 dB로 제한하고 적용하지 마.
```

**표현 MIDI 만들기**

```text
source.mid를 보존하고 새 파일을 만들어. 애프터터치를 0→80→0으로 움직이고
피치벤드는 중심 주위 ±6 cents로 흔들어줘. 악기 호환성은 별도 확인할게.
```

## 6. 승인과 문제 해결

UI와 MCP는 같은 상태 폴더(`C:\CubaseMixAI\.cubasemixai`)를 사용해야 합니다. UI는 프로젝트 루트에서 `cubasemixai ui`로 실행하고, 안내된 로컬 주소와 review token으로 엽니다.

- 기본 동작: Codex가 제안하고 사용자가 로컬 UI에서 확인·승인합니다.
- **Auto 모드:** 켜져 있는 동안 기존 및 새 미만료 변경안을 자동 승인·적용하고 목록을 자동 갱신합니다. 필요한 동안만 켜세요.
- WAV 분석, 변경 제안, Cubase 적용은 각각 별도 단계입니다. 제안 생성 요청에서 적용까지 허용하지 않았다면 실제 값은 바뀌지 않습니다.
- `cubasemixai-mcp.exe`가 없으면 가상환경에서 `python -m pip install -e .`를 실행합니다.
- 도구 목록이 갱신되지 않으면 Codex를 재시작하고 `codex mcp get cubasemixai`의 명령 경로를 확인합니다.
- 제안이 UI에 없으면 review token과 MCP/UI state directory가 일치하는지 확인합니다.
- 실제 Cubase 값이 변하지 않으면 MIDI Remote 포트, API 연결, 노출된 parameter를 확인합니다.

시스템별 한계와 남은 실기기 확인은 [검증 기록](validation.md)과 [체크리스트](verification-checklist.md)에 있습니다.
