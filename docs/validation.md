# 0.4.0 검증 기록

2026-11-09, Linux / Python 3.12.14. 정확한 의존성 버전은 [environment-tested.json](environment-tested.json)에 기록했습니다. 일반 설치는 pyproject.toml을 사용합니다.

## 자동 테스트

기존 0.3 기준 전체 suite는 **33 passed**였습니다. 이번 MIDI 표현 변경의 신규 테스트는 별도 실행해 **2 passed**했습니다. 이번 작업에서 전체 suite는 로컬 환경의 기존 MCP stdio 통합 테스트가 응답 대기에서 멈춰 완료되지 않았습니다. MCP 서버 도구 목록은 직접 조회해 29개 등록을 확인했습니다.

- 합성 사인파 RMS, 6.02dB gain/LUFS 관계, 무음·역상·구간 유효성
- 레퍼런스 기반 수치 후보의 범위·변화량, pending 상태, 근거 WAV 변경 감지
- 임베딩 점수의 동일성·무효값, DSP/CLAP 소스 해시 일치와 충돌 시 EQ 후보 보류 확인
- 프로젝트 폴더 백업/새 폴더 복원, 체크섬 손상·경로 조작·symlink 차단
- 전후 재렌더 형식·길이, 명명 구간 비교, HTML escaping, A/B LUFS·peak 여유
- 캘리브레이션 생성 확인 및 독립 관측 오차 판정
- MIDI 원본 보존, 새 파일만 생성, bounded pitch bend·CC1·channel aftertouch 확인 (신규 집중 테스트 2건 통과)
- 로컬 UI token/Host/Origin/직접 확인, 만료·거절·중복·동시 적용 차단
- 부분 전송 예외, 재시도 차단, 적용 전 스냅샷과 복원 제안
- 시뮬레이션 매핑의 승인 후 live 전송 차단
- MCP 도구 29개 등록 확인 (서버 목록 직접 조회); 승인/raw MIDI 송신 도구 부재
- 분석 → 제안 → 승인 → mock MIDI → 새 렌더 가져오기 → 평가 → A/B 출력 → 복원 제안 통합

MIDI 전송은 mock sender로 검증했으며 실제 Cubase 동작은 검증하지 않았습니다. 샌드박스에서 로컬 비동기 HTTP가 대기하여 루프백 통신 가능한 실행 환경에서 테스트를 수행했습니다.

## Cubase 15 DirectAccess 검증 추가

- 실제 배포할 ES5 driver를 Node VM의 API-shaped fake host에서 실행
- 트랙 고유 identity·scope·재정렬, 객체 교체, 현재 값 drift, edit lock, epoch 변경, request replay 거부
- API 1.3 physical conversion, API 1.2에서 1.3 기능 거부
- 설치된 catalog UID, 빈 슬롯만 할당, 삽입 child identity 확인
- Python client의 실제 SysEx chunk encoder/decoder와 실제 JS driver를 바이트 단위로 연결: handshake → 트랙 조회 → -1dB pending → 로컬 승인 → 쓰기 → fresh readback → 복원 → 빈 슬롯 삽입
- UI에서 생성한 remote 제안이 같은 SQLite 이력에 들어가고, 미승인 적용이 차단되며 승인 후 verified/복원이 동작하는지 확인
- 프로세스 간 포트 쌍 lock, Unicode/7-bit framing/chunk 충돌, setup 파일 덮어쓰기 거부

**Cubase 15 실기기 실행은 수행하지 않았습니다.** fake host는 실제 Cubase 런타임, plugin 구현, Windows MIDI 전달·host callback timing을 입증하지 않습니다. [실기기 목록](cubase15.md#8-실제-검증-목록과-한계)을 반드시 별도로 확인해야 합니다.

## 실제 CLAP 설치 및 추론

아래는 기존 0.2 분석 엔진에서 실행한 기록입니다. 0.3 제어 backend 추가가 실제 음원의 평가 정확도를 새로 입증하는 것은 아닙니다.


공식 모델 `laion/clap-htsat-unfused`를 내려받아 CPU PyTorch와 transformers로 실행했습니다.

- revision: `8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a`
- safetensors SHA-256: `abba8294f0c63d00eb3f8d998dacd16177cc5860cad3a11618e7f361a75587fe`
- `scripts/validate_ai.py`에서 3초 합성 음원과 0.5배 gain 버전을 비교
- 레벨 정규화 후 cosine similarity 약 **1.0**, 밝기·펀치·공간 프롬프트 margin 차이 **0**
- [실행 결과 JSON](ai-smoke-result.json)

이 검증은 모델 로딩·실제 임베딩/텍스트 추론·레벨 정규화 경로를 입증합니다. 실제 음악에서의 음색/펀치/공간 평가 정확도나 전문 믹싱 판단을 입증하지 않습니다. 실제 음원과 사람 청취 검증은 별도입니다.

## 실제 브라우저

`scripts/validate_browser.py`를 Chromium에서 실행했습니다.

- 로컬 토큰 입력 → WAV 분석 → 변경안 생성 → 체크박스 확인 → 승인 → MIDI 미리보기 성공
- 승인 후에도 시뮬레이션 live 전송 차단 확인
- JavaScript pageerror 없음
- 1280px 데스크톱과 390px 모바일 화면의 가로 넘침 검사 통과

UI는 사용자의 Windows Cubase PC에서 열어야 실제 파일·MIDI 장치에 접근할 수 있습니다. 스마트폰 화면 레이아웃을 지원하지만 loopback UI를 스마트폰에 공개 호스팅하지는 않습니다.

## 원격 CI와 남은 검증

GitHub Actions는 Linux/Windows Python 3.11 기본 테스트와 Linux 브라우저 검증을 실행합니다. Run workflow 수동 실행 시 공식 모델을 설치하는 AI smoke job도 실행합니다. 초기 업로드 커밋 `a162373`의 두 플랫폼 CI는 성공했습니다. 확장 커밋의 CI 상태는 [Actions](https://github.com/alsskrl-ui/CubaseMixAI/actions)에서 확인할 수 있습니다.

사용자 Windows의 설치·loopMIDI·Generic Remote·Quick Controls, 실제 `.cpr`/외부 미디어 백업 복원, 독립 true-peak 비교, 실제 음원·최종 마스터링 청취는 아직 수행하지 않았습니다. 완료 전까지 [설정·검증 목록](verification-checklist.md)을 미완료로 유지합니다.
