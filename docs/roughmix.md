# 수백 트랙 레퍼런스 러프믹스

마스터 페이더를 고정하고 최대 512트랙의 실제 WAV를 분석합니다. 전체 레퍼런스 WAV 하나면 시작할 수 있습니다. 트랙별 원래 악기 레벨을 복원하는 기능은 아닙니다. 스펙트럼 비율·현재 트랙 에너지와 출력 피크로 제한된 볼륨 후보를 계산하고 Codex가 청취·측정 근거와 함께 패닝/EQ/컴프/리버브/딜레이 변경을 제안합니다.

## 준비

1. 테스트 프로젝트를 백업하고 Cubase 15 DirectAccess·loopMIDI·MCP를 연결합니다.
2. 같은 locator, sample rate로 현재 믹스와 모든 대상 트랙을 post-fader WAV로 내보냅니다. 무음 구간을 잘라내지 않습니다. 그룹 버스와 그 하위 트랙을 중복 포함하지 않습니다.
3. `config/roughmix.example.json`을 복사합니다. Codex가 `remote_tracks`, `remote_inspect`, `remote_map_insert`로 실제 트랙 ID와 파라미터를 확인해 manifest를 작성하게 합니다. 플러그인이 없으면 `remote_find_insert`로 삽입 제안 → 승인/적용 → 다시 매핑합니다.
4. 패닝·EQ·컴프·리버브·딜레이는 `controls`에 원하는 만큼 등록합니다. `object_id`, `parameter_tag`, `unit`, `value_kind`, `max_delta`는 실제 API 값이어야 합니다. API에 없는 값은 조정할 수 없습니다. 리버브/딜레이 insert의 wet/time 또는 실제 send 파라미터를 매핑할 수 있습니다.

## Codex 요청

```text
roughmix.json을 사용해 reference.wav 기준으로 내 300트랙을 러프믹스해.
마스터 페이더는 유지하고 최종 렌더 sample peak 목표는 -6 dBFS ±0.5 dB야.
roughmix_analyze → roughmix_review를 페이지별로 읽어.
기본 볼륨 후보를 검토하고, 실제로 매핑된 pan/EQ/compressor/reverb/delay는
측정과 청취 근거가 있을 때만 개별 변경안을 만들어.
roughmix_propose로 32개씩 제안하고 기존 승인/적용 절차를 따라.
부분 실패(uncertain)는 재시도하지 말고 현재 값을 확인해.
완료 후 새 경로로 Cubase WAV를 내보내 roughmix_evaluate로 검사해.
불필요한 변화나 악화가 있으면 복원 제안을 만들고, 다음 패스는 새 스템으로 분석해.
```

`roughmix_propose(report_id, offset=0)`은 기본 볼륨 후보 32개를 만듭니다. 반환된 `next_offset`으로 다음 페이지를 진행합니다. 효과는 아래처럼 명시적으로 지정합니다.

```json
{"report_id":"실제 보고서 ID", "changes":[
  {"unique_id":"실제 트랙 ID", "control":"eq_low_gain", "delta":-1.0,
   "reason":"저역 과다 측정과 레벨 매칭 청취에 따른 보수적 후보"}
]}
```

## 적용과 반복

- 기본은 UI 승인 후 `apply`. Auto가 켜져 있으면 새 제안이 자동 적용됩니다.
- 출력 채널은 변경 대상에서 제외하고 매 변경 전후 마스터 페이더를 확인합니다.
- 효과 설정의 정답을 자동 산출하는 모델은 없습니다. Codex가 측정 결과와 실제 노출된 파라미터를 사용해 결정합니다. CLAP은 선택적 보조 근거입니다.
- 합산 위상·버스 처리·비선형 효과 때문에 볼륨 후보의 피크는 보장하지 않습니다. 새 Cubase 렌더로만 목표 도달 여부를 판정합니다. EQ/공간계 변화 후에도 재렌더해야 합니다.
- 내장 `remote_rerender_mix`는 Export 창을 여는 단계까지입니다. 실제 WAV 저장은 Cubase에서 완료하거나 별도 검증된 렌더 MCP를 연결해야 합니다. 무인 자동 렌더를 보장하지 않습니다.
- 실제 Cubase 300트랙 실기기 시험은 미완료입니다. 자동 테스트는 가짜 호스트와 합성 WAV 기준입니다.

## 기존 설치 업데이트

`git pull --ff-only` 후 가상환경에서 `python -m pip install -e .`를 실행하고 Codex를 재시작합니다. 이번 변경은 드라이버도 포함하므로 Cubase를 종료하고 설치된 `CubaseMixAI_DirectBridge.js`를 새 소스로 교체한 뒤 다시 실행해야 합니다. 드라이버 설치 위치는 [Cubase 15 가이드](cubase15.md)를 참고하세요. 재시작 후 트랙 ID와 매핑을 새로 조회합니다.
