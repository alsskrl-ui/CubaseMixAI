# 통합 기능 안내

## 통합 확인 (2026-11-20)

업데이트 전 백업의 수정 파일 10개와 새 파일 2개를 커밋 eaf3b71과 비교한 결과 모두 동일했습니다. 이 커밋은 최신 main(확인 기준 73e38d4)의 조상이며, 백업 기능은 이미 반영되어 있습니다. stash를 다시 적용할 필요가 없습니다. 백업은 유지합니다.

- 기존 수정: pyproject.toml, scripts/validate_browser.py, dashboard.html, mcp_server.py, DirectBridge 드라이버, remote/tools.py, remote/workflow.py, ui.py 및 관련 테스트.
- 당시 새 파일: remote/audio_import.py, remote/operations.py.
- 이후 확장: 세션 컨텍스트, 대규모 러프믹스와 마스터 감시, 삽입 플러그인 설정, MIDI 트랙 구간별 표현 편집.

## 기능별 진입점

| 목적 | 도구와 사용 순서 | 구분 및 제한 |
| --- | --- | --- |
| 현재 세션 파악 | remote_status → remote_tracks / remote_agent_context | 세션 폴더 분석 자료와 실제 호스트 상태를 함께 확인 |
| 여러 트랙 동일량 조정 | remote_batch_volume | unique_id 선택 또는 출력 채널을 제외한 채널에 상대 dB 제안. 한 묶음 최대 32개 |
| 명시한 트랙 감쇠 | remote_propose_lower_all_faders | target·object_id·Volume tag를 명시해 같은 양만큼 내림. 1–32개, 최대 12 dB |
| 대응 스템 비교 | remote_propose_reference_volumes | 현재/레퍼런스 스템 쌍으로 트랙별 변경량 제안 |
| 대규모 러프믹스 | roughmix_analyze → roughmix_review → roughmix_propose → roughmix_evaluate | 최대 512트랙 분석, 32개씩 적용, 마스터 변경 감시. [상세](roughmix.md) |
| 마스터 피크 조정 | remote_propose_master_peak | 트랙 조정 후 새 렌더를 측정하여 별도 마스터 변경안 생성 |
| 플러그인 검색·삽입 | remote_find_insert → 로컬 승인·적용 | 이름이 모호하면 후보 반환. 빈 슬롯에 삽입 제안 |
| 삽입 후 설정 | remote_insert_parameters → remote_configure_insert | 삽입 결과와 실제 인스턴스를 확인한 후 파라미터 변경 제안 |
| 기존 인서트 조회 | remote_map_insert / remote_inspect | 실제 객체 ID·tag·단위를 조회 |
| WAV 렌더·가져오기 | remote_rerender_mix → Cubase에서 export 완료 → finish_render_job | 렌더 명령 요청과 파일 완성은 별개. remote_import_wav로 WAV 가져오기 |
| 오디오 명령 | remote_audio_command | 선택 영역 렌더, 오디오 export/import 창 요청 |
| MIDI 표현 | midi_track_info → draw_midi_track_expression → remote_import_midi | 새 MIDI 파일을 생성해 가져옴. 기존 Cubase 파트를 직접 수정하지 않음. [상세](midi-track.md) |
| MIDI 파일 명령 | remote_midi_file_command | import/export 창 요청. 대상과 옵션은 Cubase에서 확인 |

## 승인 및 작업 흐름

1. 현재 트랙 identity와 실제 파라미터를 조회합니다.
2. 분석 근거와 작은 변경량으로 변경안을 만듭니다.
3. 로컬 UI에서 검토·승인·적용합니다. Auto는 켜져 있는 동안 모든 MCP가 새로 만든 제안을 적용합니다.
4. 적용 후 값을 재조회하고 새 WAV 렌더로 평가합니다.

페이더·플러그인 변경안은 승인 workflow를 사용합니다. WAV/MIDI 가져오기와 native 명령 도구는 호출 시 창을 열거나 파일을 제출하므로 제안 승인과 구분합니다. 전체 렌더와 파일 가져오기의 옵션·배치는 Cubase에서 확인합니다.

MCP에 노출된 모든 기능이 대시보드 작업 목록에도 있는 것은 아닙니다. 확장 도구는 Codex의 MCP 호출을 사용합니다.

## 중첩 설치 폴더의 업데이트

현재 확인한 설치의 소스 경로는 C:/CubaseMixAI/CubaseMixAI, 최초 사용한 Python은 C:/CubaseMixAI/.venv/Scripts/python.exe입니다. 내부에도 별도 .venv가 있으므로 실행 서버와 패키지를 갱신하는 Python 경로를 맞추세요.

Git 명령은 .git과 pyproject.toml이 있는 소스 폴더에서 실행해야 합니다. 로컬 변경이 있으면 먼저 내용을 확인하고 백업합니다. 이미 upstream에 반영된 stash는 재적용하지 않습니다. 최신 코드로 패키지를 설치한 뒤 실행 중인 MCP/UI 프로세스를 재시작해야 반영됩니다.

## 이번 검증 범위

백업 12개 파일과 eaf3b71의 내용 일치, 해당 커밋의 main 포함 여부를 확인했습니다. Node의 DirectBridge mock 계약 테스트도 통과했습니다. 실제 Cubase 세션 제어는 수행하지 않았습니다.
