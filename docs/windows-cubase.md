# Windows / Cubase 10.5 설치 및 실기기 검증

클라우드 Linux에서 loopMIDI 설치나 사용자의 `.cpr` 파일 백업을 수행할 수 없습니다. 아래 작업은 Cubase가 설치된 Windows PC에서 진행합니다.

## 1. 개발 환경

- Python 3.11 x64, Git for Windows, Node.js LTS를 공식 배포처에서 설치합니다. Node는 Python 엔진이 아니라 Codex CLI 설치에 사용합니다.
- `npm install -g @openai/codex` 후 `codex`에서 로그인합니다.
- `python --version`, `git --version`, `node --version`, `codex --version`으로 확인합니다.
- `git clone https://github.com/alsskrl-ui/CubaseMixAI.git` 후 루트에서 `powershell -File scripts/setup-windows.ps1`을 실행합니다. PowerShell 실행 정책을 전역으로 완화하지 마세요. 필요하면 스크립트의 명령을 직접 실행하세요.
- Tobias Erichsen 공식 사이트의 loopMIDI를 설치하고 앱에서 `CubaseMixAI` 포트를 만듭니다. Cubase보다 먼저 실행합니다.
- Cubase에서 **Back up Project**로 별도 테스트 폴더에 미디어를 포함해 백업합니다. 원본과 백업의 `.cpr` 및 오디오가 실제 존재하는지 확인합니다. 원본에서 제어 테스트하지 않습니다.

## 2. Generic Remote

처음 연결한다면 [README의 킥 Volume 화면별 가이드](../README.md#kick-volume)를 따라 위·아래 표를 각각 설정하세요. CC21 수동 테스트, 실측 dB 등록, Codex 요청 예시까지 포함되어 있습니다.

1. Cubase Studio Setup(스튜디오 설정)에서 Generic Remote를 추가합니다. Cubase 10.5의 Generic Remote이며 Cubase 12 이후 MIDI Remote API가 아닙니다.
2. MIDI Input을 `CubaseMixAI`, MIDI Output은 필요하지 않으면 Not Connected로 설정합니다. MIDI Port Setup에서 이 포트가 연주용 All MIDI Inputs로 섞이지 않게 합니다.
3. 위쪽 표의 제어 항목에 Control Change, 채널 1, 주소(CC) 20, 최대값 127, 수신 플래그를 설정합니다.
4. 아래쪽 표에서 해당 항목을 VST Mixer의 테스트 보컬 트랙 Volume에 연결합니다. 트랙 순서/이름과 선택 의존 여부를 확인하고 Generic Remote 설정을 XML로 내보내 별도 백업합니다.
5. 트랙별로 고유 채널/CC를 배정합니다. 예: vocal volume CC20, kick volume CC21, 808 volume CC22, guitar volume CC23. 번호는 추천 예시이며 실제 설정과 일치시켜야 합니다.
6. 테스트 프로젝트에서 직접 안전한 CC들을 보내 페이더 표시 dB를 기록합니다. 필요하면 독립 테스트 코드에서 `mido.open_output('CubaseMixAI')`와 `mido.Message('control_change', channel=0, control=20, value=...)`를 사용합니다. 이 수동 캘리브레이션은 앱 승인 경로 밖의 테스트이므로 테스트 복사본에서만 실행하세요.
7. 최소 두 점 이상, 특히 사용 구간 주변에 충분히 많은 `(Cubase 표시 dB, CC 정수)` 점을 기록합니다. -∞는 유한 dB가 아니므로 보간점으로 사용하지 않습니다. 비선형 구간은 점을 촘촘히 측정하고 보간 오차를 직접 확인합니다. 엄격히 증가하지 않는 파라미터는 현재 엔진으로 제어하지 않습니다.
8. 예시 매핑 파일의 points를 **실측값으로 모두 교체**하고 verified를 true로 바꿉니다. 최대 이동량은 작은 값부터 시작합니다.
9. 제안 → UI 승인 → live 적용 후 페이더의 표시값과 오차를 기록합니다. 오차가 허용 범위를 넘으면 사용을 중단하고 다시 캘리브레이션합니다.

## 3. EQ / compressor

[README의 Track Quick Controls 상세 가이드](../README.md#kick-quick-controls)를 따릅니다.

1. Kick 트랙의 Inspector Quick Controls 슬롯에 실제 compressor threshold/ratio/attack/release와 EQ gain을 할당합니다.
2. Studio Setup의 **Track Quick Controls** 장치에서 loopMIDI 입력과 슬롯별 CC30–34 수신을 설정합니다. **VST Quick Controls**와 구분합니다.
3. Kick을 선택한 상태에서 각 CC가 정확한 플러그인 파라미터를 움직이는지 확인합니다.
4. 정규화된 QC 값이 아니라 플러그인의 실제 dB/ratio/ms로 각 points와 max_delta를 따로 측정합니다. 노출되지 않는 파라미터는 수동 조작으로 남깁니다.
5. 선택 의존 QC는 대상 트랙을 선택한 한 세션에서만 검토·승인·적용합니다.

**이 경로는 현재 선택한 트랙을 따라갑니다.** 프로그램은 Cubase의 선택 트랙을 읽거나 바꾸지 못하며 `kick.*` 같은 제어 이름이 대상 선택을 강제하지 않습니다. 여러 스템의 볼륨을 Generic Remote의 실제 채널에 고정한 것과는 다른 연결입니다. 직접 고정 트랙/플러그인 파라미터를 노출하는 Generic Remote 경로가 있다면 실제 지원 여부를 별도로 확인하세요.

## 4. 실기기 수락 기록

| 항목 | 기록할 값 |
|---|---|
| Cubase / Windows / 플러그인 버전 | 실제 버전 |
| 백업 프로젝트 | 별도 폴더와 미디어 확인 |
| MIDI input / CC / channel | 포트 이름 및 XML 매핑 |
| 변경 전 / 요청 / 표시된 값 | 단위 포함, 오차 |
| 미승인 제안 적용 | 전송 차단 확인 |
| 승인 후 한 번 적용 | 화면·청취 확인 |
| 두 번째 적용 | 차단 확인 |
| 복원 제안 | 새 승인 및 값 확인 |
| 포트 연결 끊기 | uncertain 처리 확인 |
| 재렌더 WAV | 구간, sample rate, LUFS, peak, 청취 메모 |

실제 기록을 채운 후에만 roadmap의 실기기 항목을 완료 처리합니다.
