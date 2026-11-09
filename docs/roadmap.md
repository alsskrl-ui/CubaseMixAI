# 구현 상태

## 0.3 Cubase 15 확장

MIDI Remote DirectAccess 양방향 드라이버, 실제 대상/값 조회, 물리값 변환 feature detection, 호스트 compare-and-set, fresh readback, session invalidation, 빈 슬롯 plugin catalog/삽입을 추가했습니다. 기존 CC 제안과 같은 로컬 UI 승인·이력·단일 적용 경로를 사용합니다. [사용법](cubase15.md) · [공식 API/공개 저장소 조사](cubase15-api-research.md). 실제 Cubase 15 동작은 아직 실기기 검증이 필요합니다.

## 0.2 기존 분석·CC 경로

0.2.0은 모든 단계의 로컬 소프트웨어 경로를 제공합니다. Cubase 10.5에서 직접 수행해야 하는 설치·매핑·플러그인 삽입·WAV 내보내기와 실제 청취 검증은 [남은 설정·검증 목록](verification-checklist.md)에 모았습니다.

| 단계 | 구현·자동 검증된 범위 | 사용자 환경에서 남은 항목 |
|---|---|---|
| 1 개발 환경 | Python 패키지/venv, Windows 설치 스크립트, doctor, 해시 검증 백업·새 폴더 복원 | Windows 설치, loopMIDI, 실제 프로젝트/외부 미디어 복원 확인 |
| 2 제어 연결 | CC 송신, 실측 매핑 생성, 보간 및 독립 관측 오차 확인, 범위·변화량 검증 | Generic Remote/QC 연결, 각 파라미터 실측, 실기기 송신 |
| 3 DSP 분석 | WAV/LUFS/RMS/4× peak 추정/대역/다이내믹/스테레오/스템/구간 비교 | 실제 음원 및 독립 계측기와 비교 |
| 4 AI 청취 | 공식 CLAP 설치, 실제 CPU 추론, 임베딩·텍스트 프롬프트 평가, window spread, DSP 통합·근거 충돌 보류 및 소스 해시 확인 | 실제 장르별 사람 청취와 평가 일치성 검증 |
| 5 판단·승인 | EQ/볼륨/컴프레서 수치 후보, 변화량·CC 해상도 제한, 이유/위험, UI 승인·거절·전송·복원, 만료·중복 전송 차단, 이력·스냅샷 | 실제 현재 상태 확인과 청취 승인 |
| 6 MCP | stdio 도구 22개, 초기화·스키마·오류 통합 테스트, 공용 state directory | 사용자 Windows Codex 등록과 Cubase 통합 |
| 7 마스터링 | EQ/comp/limiter 매핑 계획·수치 후보, 재렌더 작업 기록·새 WAV 가져오기, 전후 DSP/AI 평가, 레벨 매칭 A/B, HTML 보고서 | Cubase 체인 실제 구성·재렌더, 독립 true-peak 확인, 최종 청취 |

판단 엔진은 설명 가능한 DSP 휴리스틱으로 제한된 수치 후보를 만들고 CLAP을 보조 근거로 통합합니다. 학습된 전문 믹싱 엔지니어 수준의 품질 보장이나 보정된 확률 신뢰도를 제공하지 않습니다. CLAP 프롬프트 점수는 절대 품질 점수가 아닙니다.
