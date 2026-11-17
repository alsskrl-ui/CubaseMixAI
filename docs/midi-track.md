# MIDI 트랙에 표현 곡선 그리기

Codex MCP로 내보낸 MIDI 파일의 **지정 트랙·채널·구간**에 피치벤드, CC1 모듈레이션, 채널 애프터터치를 그립니다. 원본 노트·템포·다른 트랙을 보존한 새 파일을 만들고 Cubase 가져오기로 연결합니다. 현재 MIDI Remote 연결에는 기존 Cubase 파트 내부의 이벤트를 직접 편집하는 API가 없으므로, 라이브 파트에 직접 그렸다고 보고하지 않습니다.

## 사용 순서

1. Cubase에서 대상 MIDI 트랙/파트를 선택합니다. `remote_midi_file_command("export_midi")`로 내보내기 창을 열고 해당 트랙의 `.mid` 저장을 완료합니다.
2. `midi_track_info(input_midi)`로 파일의 실제 track index, 채널, 길이, 기존 곡선과 SHA-256을 확인합니다. Cubase 트랙 ID와 MIDI 파일 track index는 다릅니다.
3. `draw_midi_track_expression`으로 새 `.mid`를 만듭니다. 노트를 바꾸지 않고 요청한 컨트롤러만 수정합니다.
4. `remote_import_midi(output_midi)`로 Windows Cubase 가져오기 창에 파일을 제출합니다. 실제 가져오기 완료·원래 파트 교체를 검증하는 기능은 아닙니다. 위치·템포 가져오기 옵션·악기 라우팅을 Cubase에서 확인하고 원본과 새 노트가 중복 재생되지 않게 합니다. 다중 트랙 파일은 다른 트랙도 포함하므로 가능하면 대상 트랙만 내보내세요.

## Codex 요청 예시

```text
내보낸 lead.mid의 트랙 목록과 채널을 먼저 확인해줘.
Lead 트랙의 0~8박 구간에 피치벤드를 0 → +2반음 → 0으로,
모듈레이션은 0 → 80 → 0으로 그려 lead-expression.mid로 저장해.
악기의 피치벤드 범위는 ±2반음이야.
기존 노트는 유지하고 기존 곡선이 있으면 교체 전에 알려줘.
파일을 만든 뒤 Cubase MIDI 가져오기로 제출해줘.
```

```json
{
  "input_midi": "C:/session/lead.mid",
  "output_midi": "C:/session/lead-expression.mid",
  "track_index": 1,
  "channel": 1,
  "start_beat": 0,
  "end_beat": 8,
  "pitch_curve": [[0,0],[0.5,2],[1,0]],
  "modulation_curve": [[0,0],[0.5,80],[1,0]],
  "pitch_bend_range_semitones": 2,
  "steps_per_beat": 32,
  "replace_existing": false
}
```

위 `track_index`·채널·구간은 예시이며 `midi_track_info` 결과로 바꿉니다. `expected_sha256`에 조회한 해시를 넣으면 조회 후 변경된 파일을 차단합니다.

- `channel`: **1~16**, `track_index`: **0부터 시작**. 기존 `add_midi_expression`의 channel(0~15)과 다릅니다.
- 박자는 MIDI 파일 시작점 기준 **0부터 시작하는 4분음표 단위**입니다. Cubase의 마디 번호가 아닙니다. 템포 변화가 있어도 박자 위치는 유지합니다.
- 곡선 위치는 선택 구간의 0~1 비율, 피치는 **반음 단위**, CC1/애프터터치는 0~127입니다. ±6 cents 흔들림은 ±0.06반음 지점을 번갈아 지정합니다.
- 최대 64개 지점을 선형 보간합니다. 마지막 지점은 구간 끝 직전 tick에 쓰고, 끝에서는 원래 컨트롤러 상태로 복귀합니다.
- `replace_existing=true`일 때만 선택 구간의 요청한 컨트롤러를 교체합니다. 다른 CC·채널·노트는 보존합니다. 원본 파일과 기존 출력 파일을 덮어쓰지 않습니다.
- 악기의 pitch-bend 범위는 직접 맞춰야 합니다. 같은 라우팅 채널의 동시 발음에 함께 작용하며, CC1/애프터터치 반응은 악기 지원에 따릅니다.

이번 업데이트는 Python 패키지 갱신, MIDI Remote JS 드라이버 교체, Cubase/Codex 재시작이 필요합니다. 실제 Cubase MIDI 가져오기와 악기별 청취 검증은 사용자 PC에서 진행합니다.
