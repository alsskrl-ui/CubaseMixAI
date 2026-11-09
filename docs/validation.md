# 검증 기록

2026-11-09, 클라우드 Linux / Python 3.12.14에서 기본 의존성을 설치하고 8개 테스트를 통과했습니다. `requirements-tested.txt`는 이 환경의 버전 기록이며 Windows/Python 3.11용 잠금 파일은 아닙니다. 일반 설치는 pyproject.toml을 사용합니다.

- 합성 1kHz 사인파의 RMS와 6.02dB gain/LUFS 차이
- 무음 및 역상 스테레오, 잘못된 구간 처리
- 미승인 live 전송 차단, 토큰·origin·직접 확인 검증
- 승인 후 단일 전송과 역방향 복원 제안
- 매핑 변경 감지와 유효 상태 검증
- 부분 전송 예외 및 자동 재전송 차단
- 동시 적용 요청 중 한 번만 송신
- 비유한 값/변화량 한계/미검증 매핑 거부
- MCP stdio 초기화, 8개 도구 조회, 승인 도구 부재, 존재하지 않는 제안 적용 오류

명령: `python -m pytest -q` → `8 passed`. FastAPI/Starlette의 httpx TestClient 사용 중단 예정 경고 1건이 있으며 테스트는 통과했습니다. GitHub Actions에는 Linux와 Windows Python 3.11 테스트를 설정했지만 원격 CI 결과는 별도 확인이 필요합니다.

샌드박스에서 로컬 비동기 HTTP 테스트가 대기하여, 동일 테스트를 네트워크/루프백 통신이 가능한 실행 환경에서 완료했습니다. 실제 MIDI 장치는 mock sender로 대체했습니다. 실기기, 사용자 음원, CLAP 모델, Windows 설치 및 UI 브라우저 수동 청취 검증은 수행하지 않았습니다.
