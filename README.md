# CubaseMixAI

레퍼런스 WAV와 믹스/스템을 분석하고, Cubase 상태를 읽어 믹스 변경안을 제안하는 로컬 도구입니다. Codex는 MCP로 분석·제안·Cubase 제어 도구를 호출합니다. 실제 변경은 기본적으로 로컬 승인 UI에서 승인해야 합니다.

## 할 수 있는 일

- WAV의 LUFS, peak, RMS, 주파수, 다이내믹, 스테레오 분석과 선택적 CLAP 청취 비교
- 준비된 대응 스템 기반 페이더 제안, 선택한 여러 트랙의 동일량 페이더 조정, 렌더 peak 목표 제안
- Cubase API로 트랙·페이더·플러그인 상태 조회, 지원되는 플러그인 삽입/파라미터 제안
- 애프터터치·모듈레이션·피치벤드가 포함된 MIDI 파일 생성
- 레퍼런스/분석 파일을 읽고 현재 Cubase 세션과 함께 제안하는 에이전트 workflow

완성된 레퍼런스 WAV 하나만으로 개별 악기의 레벨이나 페이더를 알아낼 수는 없습니다. 레퍼런스 악기별 직접 비교에는 대응 스템이 필요합니다. 새 러프믹스는 전체 레퍼런스와 내 트랙별 WAV로 제한된 밸런스 후보를 계산합니다. 지원 여부는 Cubase 버전과 API가 노출하는 값에 따릅니다.

## Windows 빠른 설치

```powershell
git clone https://github.com/alsskrl-ui/CubaseMixAI.git C:\CubaseMixAI
cd C:\CubaseMixAI
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e .
codex mcp add cubasemixai --env 'CUBASEMIXAI_STATE_DIR=C:\CubaseMixAI\.cubasemixai' -- 'C:\CubaseMixAI\.venv\Scripts\cubasemixai-mcp.exe'
codex mcp list
```

Cubase 연결에는 Cubase 15 DirectAccess 설정과 loopMIDI 포트가 필요합니다. CLAP은 선택 사항입니다: `pip install -e ".[ai]"`. 승인 UI 실행법과 연결 단계는 [Windows 빠른 가이드](docs/windows-codex-manual.md)를 참고하세요.

## Codex 요청 예시

```text
remote_agent_context로 C:/CubaseMixAI/session을 읽고 분석 결과와 현재 Cubase 트랙/페이더를 요약해줘.
스템 매핑이 확인된 트랙만 최대 1 dB 변경안으로 제안하고 적용은 하지 마.
```

제안은 UI에서 확인·승인합니다. UI의 Auto 모드는 켜져 있는 동안 기존 및 새 미만료 변경안을 자동 승인·적용하고 목록을 자동 갱신합니다. 필요할 때만 켜고 작업 후 끄세요.

## Cubase Complete MCP 선택 연동

프로젝트·transport·MIDI import/export·WAV 렌더 기능은 별도 [Cubase Complete MCP 통합 가이드](docs/cubase-integration.md)를 참고하세요. 기존 CubaseMixAI 기능과 서버는 그대로 유지됩니다.

## 문서

- [Windows 설치·Codex·승인 UI 가이드](docs/windows-codex-manual.md)
- [Cubase 15 API 기능 및 한계](docs/cubase15.md)
- [세션 분석 설정 예시](config/agent-session.example.json)
- [검증 기록](docs/validation.md)
- [남은 검증 항목](docs/verification-checklist.md)

## 수백 트랙 러프믹스

레퍼런스와 최대 512트랙 WAV를 측정해 서로 다른 볼륨 후보를 만들고, Codex가 매핑된 패닝·EQ·컴프·리버브·딜레이를 개별 제안할 수 있습니다. 마스터 페이더를 고정하고 32개씩 승인·적용한 뒤 새 렌더로 −6 dBFS peak 목표를 확인합니다. 실제 렌더는 Cubase에서 완료해야 합니다. [준비·사용 예시](docs/roughmix.md).

플러그인 작업은 **검색·삽입 제안 → 승인/삽입 확인 → 실제 파라미터 조회 → 설정 변경 제안·적용** 순서입니다. `remote_insert_parameters`와 `remote_configure_insert`가 삽입 결과에 연결되어 잘못된 인스턴스 조정을 막습니다. [사용 순서](docs/roughmix.md#플러그인-불러오기--파라미터-조정).

## MIDI 트랙 표현

`midi_track_info` → `draw_midi_track_expression` → `remote_import_midi`로 지정 MIDI 트랙·채널·박자 구간의 피치벤드·모듈레이션·애프터터치를 편집합니다. 새 MIDI 파일을 만들어 가져오는 방식이며 기존 Cubase 파트를 직접 수정하지 않습니다. [사용 예시](docs/midi-track.md).
