# CubaseMixAI 0.4

레퍼런스 WAV를 분석하고, Cubase 믹스 변경안을 검토하며, MIDI 표현이 들어간 새 파일을 만드는 로컬 도구입니다. Codex는 분석·조회·제안을 돕고, Cubase 변경은 사용자가 로컬 승인 UI에서 승인해야 적용됩니다.

## 필요한 기능과 현재 범위

| 기능 | 현재 동작 | 예시 및 제한 |
|---|---|---|
| 레퍼런스 WAV 분석 | LUFS, RMS, peak 추정치, 주파수 대역, 다이내믹, 스테레오를 측정하고 믹스와 비교합니다. CLAP 청취 비교는 선택 설치입니다. | “후렴의 믹스와 레퍼런스 WAV를 비교해 음량·저역·펀치 차이를 알려줘.” 분석값은 참고 근거이며 자동 EQ 정답은 아닙니다. |
| MIDI 표현 조정 | MIDI 파트의 새 복사본에 피치벤드, 모듈레이션(CC1), 채널 애프터터치를 제한된 범위로 생성합니다. | “이 MIDI를 복사해 피치가 최대 6 cents 정도 불안하게 흔들리는 버전을 만들어줘.” WAV에는 MIDI 이벤트가 없으므로 WAV 스템만으로는 적용할 수 없습니다. Cubase에서 결과 MIDI를 직접 가져와 들어봐야 합니다. |
| 믹싱 조정 | Cubase 15 MIDI Remote가 노출한 트랙·파라미터를 읽고, 변경안을 만들어 승인 후 적용하고 실제 값을 다시 읽습니다. | “Kick Volume을 현재보다 1 dB 낮추는 안을 만들어. 아직 적용하지 마.” 레퍼런스 분석 결과를 Cubase 파라미터 변경안으로 자동 연결하는 과정은 아직 수동 검토가 필요합니다. |
| 마스터링 | WAV 전후 비교와 마스터 EQ·컴프레서·리미터 후보/체크리스트를 제공합니다. | “레퍼런스와 마스터 WAV의 음량·톤·피크 차이를 비교해줘.” 플러그인 체인 자동 구성, WAV 자동 렌더, 음질 최종 판정은 하지 않습니다. |
| 플러그인 불러오기·조정 | Cubase API가 지원하면 설치 목록을 조회하고 빈 Insert 슬롯에 승인 후 삽입합니다. 노출된 플러그인 파라미터는 조회·제안·승인 후 조정할 수 있습니다. | “빈 슬롯과 사용할 수 있는 플러그인을 보여줘. 삽입하지 말고 기다려.” 기존 플러그인 교체·삭제와 숨겨진 파라미터 조정은 지원하지 않습니다. |

**CLAP**은 선택 설치하는 오디오·텍스트 유사도 모델입니다. “더 밝다”, “펀치감이 있다”, “공간감이 넓다” 같은 설명과 WAV가 얼마나 어울리는지 비교해 DSP 분석을 보완합니다. 음질 점수나 EQ 정답을 주는 모델은 아니며, 최종 판단은 레벨을 맞춰 직접 들어야 합니다. 사용법은 [짧은 CLAP 가이드](docs/windows-codex-manual.md#clap)를 참고하세요.

## 권장 작업 순서

1. Cubase에서 레퍼런스 WAV, 현재 믹스 WAV, 필요한 스템 WAV를 같은 구간 기준으로 내보냅니다.
2. Codex에 파일을 분석·비교하게 하고, 결과와 불확실성을 확인합니다.
3. 믹싱·마스터링 변경은 대상 트랙/파라미터와 목표를 정해 pending 제안으로 만듭니다.
4. 로컬 승인 UI에서 대상·현재값·목표값을 확인해 직접 승인합니다. 적용 후 Cubase 값과 소리를 확인합니다.
5. 악기 표현을 바꿀 때는 해당 파트의 MIDI 파일을 별도로 내보내 새 표현 MIDI를 만들고 Cubase에 가져와 A/B 청취합니다.
6. Cubase에서 새 WAV를 렌더하고 레퍼런스와 비교해 최종 결정을 합니다.

## Codex에 요청하는 예

```text
mix.wav와 reference.wav의 후렴 구간을 비교해 LUFS, 저역, 다이내믹 차이를 설명해줘.
아직 Cubase 값을 바꾸지 말고 측정 결과와 불확실성을 먼저 보여줘.
```

```text
kick.mid를 expressive.mid로 복사해 피치가 최대 6 cents 범위에서 천천히 불안하게 움직이게 해줘.
악기의 pitch-bend range는 2 semitones야. 원본은 보존하고 결과 경로를 알려줘.
```

```text
Cubase 15에서 Kick 트랙의 실제 Volume과 Insert 슬롯을 조회해줘.
레퍼런스 분석을 근거로 가능한 변경안을 설명하고, 제안만 만들어. 적용하지 마.
```

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
