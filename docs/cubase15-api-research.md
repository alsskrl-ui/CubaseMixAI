# Cubase 15 제어 API 조사와 0.3 설계

조사일: 2026-11-09. 공식 API 문서와 공개 저장소의 실제 구현을 읽고 비교했습니다. 외부 프로젝트가 주장하는 live 검증과 CubaseMixAI 자체 검증은 다릅니다.

## 핵심 발견

Steinberg 공식 [MIDI Remote API 1.3 release notes](https://steinbergmedia.github.io/midiremote_api_doc/new_in_v1.3/)는 지원 호스트로 **Cubase/Nuendo 15**를 명시합니다. DirectAccess에 물리값 변환·파라미터 메타데이터·플러그인 관리 기능이 추가되었습니다. 따라서 Cubase 10.5의 Generic Remote 제약을 Cubase 15에도 그대로 적용하면 안 됩니다.

공식 [DirectAccess 설명](https://steinbergmedia.github.io/midiremote_api_doc/advanced-topics/direct-access/)과 [API 선언](https://github.com/steinbergmedia/midiremote_api_doc/blob/b099a86923b248ddd30546a4869c9eeb42ab4c5d/generated-ide-assets/v1/midiremote_api_v1.d.ts)에서 다음 계약을 확인했습니다.

- `makeDirectAccess`, `getBaseObjectID`, `getChildObjectID`, `getObjectUniqueIDString`: 호스트 객체 계층과 식별자 조회
- `getParameterTagByIndex`, `getParameterProcessValue`, `getParameterDisplayValue`: 실제 값과 파라미터 식별
- `setParameterProcessValue`: 0–1 정규화 값 쓰기
- `getParameterDisplayUnits`, `convertParameterProcessValueToPlain`, `convertParameterPlainToProcessValue`: 단위 및 물리값 변환
- `mPluginManager.getPluginCollectionByIndex`: 슬롯에 사용 가능한 설치 플러그인 목록
- `mPluginManager.trySetSlotPlugin`: UID로 슬롯 플러그인 할당
- `CommandBinding.canPerform`: Key Command 실행 가능 여부. 실행 결과를 입증하는 기능은 아님

API 1.3 기능은 버전 문자열만으로 판단하지 않고 메서드 존재 여부로 탐지합니다. 공개 참고 프로젝트는 Cubase 15.0.10을 API 1.2, 15.0.30을 API 1.3 검증 대상으로 구분합니다. **모든 Cubase 15 설치가 같은 API를 제공한다고 가정하지 않습니다.**

## 검토한 경로

| 경로 | 장점 | 한계 / 이번 선택 |
|---|---|---|
| MIDI Remote API 1.2/1.3 + DirectAccess | 실제 객체·파라미터 읽기/쓰기, 대상 식별, 1.3 물리값·plugin manager | **새 주 제어 백엔드로 구현.** 노출되지 않은 객체/값은 거부 |
| Generic Remote + CC | Cubase 10.5 기존 프로젝트에 사용, 단순 전송 | 기존 경로 유지. 7-bit 값·실측 보간·호스트 readback 부재 |
| Track / Focus Quick Controls | 노출된 플러그인 파라미터 연결 | 선택/포커스 의존. 새 DirectAccess 경로에서 대체 가능한 대상은 직접 주소로 제어 |
| Mackie Control / MCU | mixer/transport 제어에 널리 사용되는 MIDI 프로토콜 | bank/선택·플러그인 주소 문제를 별도로 풀어야 하므로 이번 주 경로로 채택하지 않음 |
| VST3 SDK | VST 플러그인 개발·호스팅 SDK | Cubase 프로젝트 전체 원격 제어 API가 아님. 플러그인 개발 시 별도 검토 |
| SKI / Cubase iC 계열 | 전용 원격 제어 경로로 알려져 있음 | 이번 조사에서 공개 사용 가능한 SDK/계약을 확인하지 못했으므로 지원을 주장하지 않음 |
| OSC / HTTP / MCP bridge | 다른 프로세스/AI 클라이언트와 연결하기 편리 | bridge가 실제 어떤 Cubase API를 호출하는지가 핵심. Cubase의 범용 native REST/OSC API가 있다고 가정하지 않음 |
| Key Commands + Windows UI Automation/OCR | 프로젝트 저장·대화상자·WAV 내보내기 보조 가능 | 해상도·언어·대화상자 상태와 후조건 검증 필요. 이번 구현은 export 버튼 자동화를 추가하지 않음 |

## 참고 저장소와 판독 범위

1. **[steinbergmedia/midiremote_api_doc](https://github.com/steinbergmedia/midiremote_api_doc)** — 공식 문서. revision `b099a86923b248ddd30546a4869c9eeb42ab4c5d`. API 선언, 1.3 release notes, DirectAccess, Getting Started를 확인했습니다.
2. **[muhwagwa0112/cubase-complete-mcp](https://github.com/muhwagwa0112/cubase-complete-mcp)** — MIT. revision `f3f88b003767df6eb056221d9731ff4870a0db22`. README, capability matrix, driver generator, SysEx protocol을 검토했습니다. Windows .NET broker, 대상 식별, fresh read와 API 1.3 plugin manager 경로를 참고했습니다. 이 프로젝트의 live-validated 표시는 해당 프로젝트의 주장/기록이며 우리 프로그램의 live 검증을 의미하지 않습니다.
3. **[takezou621/cubase-midi-remote-api](https://github.com/takezou621/cubase-midi-remote-api)** — revision `49dad6b382d912ccb88643e09b2bc643d4a96078`. README와 MIDI Remote JS bridge를 검토했습니다. mixer bank·QC·SysEx 피드백·DirectAccess 구조를 비교했습니다. 조사 시 루트 LICENSE를 확인하지 못했으며 코드를 복제하지 않았습니다.
4. **[steinbergmedia/vst3sdk](https://github.com/steinbergmedia/vst3sdk)** — 공식 VST3 SDK. MIDI Remote와 목적이 다른 경로로 분류했습니다.
5. **[abrahamjeyaraj/faderport-classic-mcu](https://github.com/abrahamjeyaraj/faderport-classic-mcu)** — MCU 관련 공개 후보로 검색했습니다. revision `e777b0deae6be4804d79edf4554c301c4a17519f`. 상세 소스/API 호환성 검증은 하지 않았으며 구현 의존성으로 사용하지 않습니다.

이번 JS/Python bridge·프로토콜·승인 상태 관리는 CubaseMixAI에서 새로 작성했습니다. 참고 저장소 전체를 설치하거나 실행하지 않았으며, 외부 코드를 검증 없이 우리 runtime으로 가져오지 않았습니다.

## 0.2 → 0.3의 구체적 개선

| 항목 | 기존 CC 경로 | 새 MIDI Remote 경로 |
|---|---|---|
| 대상 | 수동 CC 주소, QC는 선택 트랙 의존 | 호스트 session + channel/object unique ID + parameter tag |
| 현재 값 | 사용자가 입력 | Cubase DirectAccess로 조회 |
| 변환 | 측정한 dB/CC 선형 보간 | 1.3이 노출하면 호스트 plain/normalized 변환; 없는 기능은 명시적 정규화 값만 사용 |
| 승인 이후 상태 변경 | 근거 파일/매핑 해시만 검사 | 실제 대상·파라미터 메타데이터·현재 값·변환 결과를 dispatch callback에서 재검사 |
| 적용 결과 | MIDI send 완료 | 별도 fresh read가 목표 normalized 값과 일치할 때 `verified` |
| plugin 삽입 | 수동 | API 1.3 catalog UID로 **빈 슬롯만** 승인 후 할당, 실제 child UID 확인 |
| 프로젝트 전환 | 수동 확인 필요 | driver 재활성화 session 변경 시 이전 target/제안 거부 |
| 동시 접근 | 제안당 중복 전송 차단 | 제안당 차단 + 포트 쌍 전역 프로세스 lock + driver request replay 차단 |

`verified`는 호스트 파라미터/플러그인 identity 후조건을 관찰했다는 뜻입니다. 소리의 개선, 모든 automation 동작, Cubase 실제 호환성을 보장하는 말이 아닙니다. 현재 자체 검증은 fake host·프로토콜·Python·브라우저·CI이며 **Cubase 15 실기기 검증은 아직 필요**합니다.
