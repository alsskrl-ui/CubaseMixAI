# CubaseMixAI 0.4

레퍼런스 WAV를 분석하고, Cubase 믹스 변경안을 검토하며, MIDI 표현이 들어간 새 파일을 만드는 로컬 도구입니다. Codex는 분석·조회·제안을 돕고, Cubase 변경은 사용자가 로컬 승인 UI에서 승인해야 적용됩니다.

## 필요한 기능과 현재 범위

| 기능 | 현재 동작 | 예시 및 제한 |
|---|---|---|
| 레퍼런스 WAV 분석 | LUFS, RMS, peak 추정치, 주파수 대역, 다이내믹, 스테레오를 측정하고 믹스와 비교합니다. CLAP 청취 비교는 선택 설치입니다. | “후렴의 믹스와 레퍼런스 WAV를 비교해 음량·저역·펀치 차이를 알려줘.” 분석값은 참고 근거이며 자동 EQ 정답은 아닙니다. |
| MIDI 표현 조정 | MIDI 파트 복사본에 피치벤드·모듈레이션(CC1)·채널 애프터터치를 랜덤하게 또는 지정한 곡선으로 넣습니다. | “이 MIDI에 애프터터치를 처음 0, 중간 80까지 올려 유지하고 끝에서 0으로 내리는 곡선을 넣어줘.” WAV에는 MIDI 이벤트가 없어 MIDI 파트가 필요하며, 결과를 Cubase로 가져와야 합니다. |
| 믹싱 조정 | Cubase 15에서 선택한 여러 트랙 페이더를 대응 스템 WAV와 비교해 하나의 승인 묶음으로 제안할 수 있습니다. | 트랙별 현재/레퍼런스 스템 쌍과 실제 Cubase Volume 태그를 명시해야 합니다. 기존 단일 파라미터 조정도 가능합니다. |
| 마스터링 | WAV 전후 비교와 EQ·컴프레서·리미터 후보/체크리스트를 제공합니다. 트랙 조정 후 새 마스터 WAV 피크를 측정해 마스터 페이더 제안을 별도로 만들 수 있습니다. | 목표는 마스터 페이더 위치가 아니라 기본적으로 출력 sample peak -6 dBFS입니다. 조정 후 다시 렌더·측정해야 하며, 자동 WAV 렌더와 최종 음질 판정은 하지 않습니다. |
| 플러그인 불러오기·조정 | Cubase API가 지원하면 설치 목록을 조회하고 빈 Insert 슬롯에 승인 후 삽입합니다. 노출된 플러그인 파라미터는 조회·제안·승인 후 조정할 수 있습니다. | “빈 슬롯과 사용할 수 있는 플러그인을 보여줘. 삽입하지 말고 기다려.” 기존 플러그인 교체·삭제와 숨겨진 파라미터 조정은 지원하지 않습니다. |

**CLAP**은 선택 설치하는 오디오·텍스트 유사도 모델입니다. “더 밝다”, “펀치감이 있다”, “공간감이 넓다” 같은 설명과 WAV가 얼마나 어울리는지 비교해 DSP 분석을 보완합니다. 음질 점수나 EQ 정답을 주는 모델은 아니며, 최종 판단은 레벨을 맞춰 직접 들어야 합니다. 사용법은 [짧은 CLAP 가이드](docs/windows-codex-manual.md#clap)를 참고하세요.

## 권장 작업 순서

1. Cubase에서 레퍼런스 WAV, 현재 믹스 WAV, 필요한 스템 WAV를 같은 구간 기준으로 내보냅니다.
2. Codex에 파일을 분석·비교하게 하고, 결과와 불확실성을 확인합니다.
3. 현재/레퍼런스의 대응 스템과 Cubase Volume 파라미터를 지정해 `remote_propose_reference_volumes` 묶음 제안을 만듭니다.
4. 로컬 승인 UI에서 트랙별 측정치·변경폭을 확인해 한 번 승인합니다. Cubase는 페이더를 순차 변경하므로 적용 후 전체를 확인합니다.
5. 조정된 세션에서 새 마스터 WAV를 렌더한 뒤 `remote_propose_master_peak`으로 sample peak를 -6 dBFS 쪽으로 옮기는 별도 제안을 만듭니다. 승인·적용 후 다시 렌더해 측정합니다.
6. 악기 표현을 바꿀 때는 해당 MIDI 파트를 별도로 내보내 새 표현 MIDI를 만들고 Cubase에 가져와 A/B 청취합니다.
7. 레벨을 맞춰 레퍼런스와 비교하고 최종 청취합니다.

## Codex에 요청하는 예

```text
mix.wav와 reference.wav의 후렴 구간을 비교해 LUFS, 저역, 다이내믹 차이를 설명해줘.
아직 Cubase 값을 바꾸지 말고 측정 결과와 불확실성을 먼저 보여줘.
```

```text
kick.mid를 expressive.mid로 복사해 채널 애프터터치 곡선을 그려줘:
처음 0, 25% 지점 15, 60% 지점 90까지 올리고 80%까지 유지,
끝에서 0으로 내려줘. MIDI 파일에 이벤트로 넣고 원본은 보존해.
Cubase 화면에 직접 그린 것처럼 말하지 말고 결과 경로를 알려줘.
```

```text
Cubase 15에서 Kick 트랙의 실제 Volume과 Insert 슬롯을 조회해줘.
레퍼런스 분석을 근거로 가능한 변경안을 설명하고, 제안만 만들어. 적용하지 마.
```

여러 페이더를 한 번에 제안하려면 현재 믹스의 각 트랙 WAV와 대응하는 레퍼런스 트랙 WAV가 필요합니다. Codex에는 어떤 두 파일이 서로 대응하는지 명시하고 `remote_propose_reference_volumes`를 호출하게 하세요. 한 번의 로컬 승인으로 묶음 전체를 승인합니다. 페이더 변경 후 렌더한 마스터 WAV 피크를 -6 dBFS에 맞추려면 `remote_propose_master_peak`으로 별도 제안합니다.

피치벤드 범위는 악기 설정과 일치해야 합니다. 피치벤드와 채널 애프터터치는 같은 MIDI 채널의 동시에 울리는 음에 함께 작용합니다. CC1·애프터터치는 악기와 프리셋이 지원해야 들립니다.

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
