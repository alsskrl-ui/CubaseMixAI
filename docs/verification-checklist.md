# 남은 설정·검증 목록

**Cubase 15의 새 DirectAccess 경로는 [전용 가이드의 실기기 검증 목록](cubase15.md#8-실제-검증-목록과-한계)을 먼저 확인하세요.** 아래 Generic Remote/QC 항목은 기존 10.5 CC 경로용입니다.

소프트웨어 자동 테스트와 실제 CLAP/브라우저 smoke test를 통과한 뒤, **사용자의 Windows PC·Cubase·실제 음원에서 확인해야 할 항목만** 추렸습니다. 아래 항목은 원격 클라우드의 테스트로 대체할 수 없습니다.

## 1. Windows와 프로젝트 보존
- [ ] 사용자 PC에서 Python 3.11+, Git, Node, Codex 설치 확인: `cubasemixai doctor`
- [ ] loopMIDI 설치 → `CubaseMixAI` 포트 생성 → `cubasemixai ports`에 표시 확인
- [ ] Cubase Back up Project로 외부 미디어까지 모은 테스트 복사본 생성
- [ ] Cubase 저장·종료 후 `backup` → `verify-backup` → 새 폴더 `restore-project`; 복원한 `.cpr`을 Cubase에서 실제 열어 누락 미디어가 없는지 확인

## 2. Cubase 제어와 승인
- [ ] Generic Remote 입력을 loopMIDI 포트에 연결하고 연주용 All MIDI Inputs와 MIDI 루프가 없는지 확인
- [ ] 트랙·채널·CC를 하나씩 확인; 트랙 순서 변경 후 잘못된 트랙이 움직이지 않는지 확인
- [ ] 볼륨 dB/CC 실측점 등록; **보간에 사용하지 않은 값**으로 `calibration-check` 수행하여 허용 오차 통과
- [ ] EQ gain과 compressor threshold/ratio/attack/release의 Quick Control 매핑·단위·실측 범위를 각각 확인
- [ ] 미승인/거절/만료 제안은 실기기에 아무 MIDI도 보내지 않는지 확인
- [ ] 승인 후 한 번 적용 → 두 번째 적용 차단 → Cubase 표시값·청취 확인
- [ ] 복원 제안을 새로 승인한 뒤 원래 값으로 돌아가는지 확인
- [ ] 포트 단절/전송 중 종료 시 실제 부분 적용 여부를 확인하고 `uncertain`/`sending`을 자동 재시도하지 않는지 확인

## 3. 실제 음원과 AI 청취
- [ ] 레퍼런스·믹스·킥/808/보컬/기타 스템을 실제 WAV로 분석하고 DAW/독립 계측기의 LUFS/RMS와 비교
- [ ] intersample peak가 있는 음원을 인증 true-peak 미터로 확인; 현재 4× 추정값의 오차 기록
- [ ] 후렴/드롭을 서로 대응하는 구간으로 내보내 비교; 다른 편곡/구간을 잘못 비교하지 않는지 확인
- [ ] Windows에서 CPU CLAP 설치·모델 다운로드·실제 추론 확인 (`setup-ai`, `listen`)
- [ ] 같은 장르의 실제 음원으로 밝기·펀치·공간 프롬프트 점수와 사람의 레벨 매칭 청취가 맞는지 기록; 신뢰도는 확률로 해석하지 않기
- [ ] 과도한 EQ/컴프레션/공간감 변화가 있는 테스트 음원에서도 모델의 오판·불확실성 확인

## 4. MCP와 최종 마스터
- [ ] 사용자 Windows Codex에 MCP 등록; CLI/UI/MCP의 state directory가 같고 22개 도구가 조회되는지 확인
- [ ] Codex 분석 → 변경안 → **브라우저 직접 승인** → 실기기 적용까지 통합 확인
- [ ] Cubase 마스터 버스에 EQ → compressor → true-peak limiter를 직접 삽입; 순서·bypass·oversampling·실제 QC 대상 확인
- [ ] master 변경안 검토·승인·적용 후 같은 locator/sample rate/channels로 WAV 재렌더
- [ ] `render-finish` / `evaluate --model-dir`로 DSP/AI 재비교, `ab`로 출력 레벨을 맞춘 뒤 청취
- [ ] clipping·위상·저역·보컬 명료도·펀치·다이내믹·노이즈를 확인하고 사람의 청취로 개선 여부 최종 결정

## 현재 API 범위에서 자동화하지 않는 조작

Cubase 10.5 Generic Remote는 내부 프로젝트 전체 상태 조회, 임의 플러그인 삽입, Export Audio Mixdown 실행 API를 제공하지 않습니다. 이 세 조작은 Cubase에서 직접 수행합니다. 구현한 백업은 디스크에 저장된 폴더, 현재 값은 사용자가 확인한 입력값, 재렌더는 새 WAV 가져오기 방식입니다. GUI 좌표 자동화로 이를 완료 처리하지 않습니다.
