# 10. 모델링 가이드 (서버 랙)

- 상태: 채택 (2026-10-15)
- 목적: 서버 랙을 직접 모델링할 때 지킬 크기, 구성, 점검 항목, 내보내기 방법을 정한다.
- 읽는 사람: 모델링을 하는 사람. Blender를 쓸 수 있고 3D 모델링 경험이 많지 않아도 따라 할 수 있게 쓴다.
- 관련 문서: [09 USD 규격](09_usd_spec.md)

## 1. 토폴로지가 어려울까? (결론부터)

**이 프로젝트에서는 걱정하지 않아도 된다.** 토폴로지(면과 선이 이어진 방식)가 중요한 경우와 아닌 경우가 다르다.

| 토폴로지가 중요한 경우 | 이 프로젝트의 랙 |
|---|---|
| 캐릭터처럼 **휘어지는** 모델(관절, 표정) | 랙은 딱딱하고 움직이지 않는다. |
| 서브디비전으로 **부드럽게 만드는** 모델 | 쓰지 않는다. 각진 장비다. |
| 조각(스컬프팅)이나 리토폴로지가 필요한 모델 | 하지 않는다. |
| 애니메이션이 있는 모델 | 없다. 문도 움직이지 않는다. |

대신 **아래 항목이 결과 품질을 좌우한다.** 토폴로지보다 이쪽에 신경 쓴다.

| 중요한 것 | 이유 |
|---|---|
| 크기와 원점 | 장면에 놓았을 때 크기가 맞고 위치 계산이 쉬워야 한다. |
| 법선(면이 향하는 방향) | 뒤집히면 조명이 어둡게 나온다. |
| 삼각형 개수 | 랙 20기를 한 화면에 그려야 한다. |
| 이름과 재질 칸 | 스크립트와 Unreal이 이름으로 부품을 찾는다. |
| 모디파이어 적용 | 적용하지 않으면 내보낸 모양이 다를 수 있다. |

**만드는 방식은 "하드 서피스"**: 상자 같은 기본 도형을 키우고, 자르고, 모서리를 깎는(베벨) 방식이다. Blender의 모디파이어(어레이, 미러, 베벨, 불리언)로 대부분 만든다.

## 2. 크기와 구성

| 항목 | 값 | 설명 |
|---|---|---|
| 랙 외형 | 가로 60 x 깊이 100 x 높이 200 cm | 가상 값. 실제 제품 치수를 따라 하지 않는다. |
| 서버 1U | 4.445 cm | 19인치 랙의 공개 표준 높이 |
| 서버 폭 | 48.26 cm | 19인치의 표준 폭 |
| 원점 | 바닥 면의 중앙 | 배치할 때 편하다. |
| 앞쪽 | -Y 방향 | 서버 앞면이 -Y를 향한다. |
| Blender 단위 | 1 단위 = 1 cm | 블록아웃 파일이 이미 설정되어 있다. |

**꼭 있어야 하는 오브젝트**

| 이름 | 내용 | 비고 |
|---|---|---|
| `Rack` | 맨 위 빈 오브젝트. `assetType = rack` | 기본 prim이 된다. |
| `Frame_*` | 바닥판, 윗판, 기둥 | 이름 앞부분만 맞으면 된다. |
| `Server_U##` | 서버. 이름의 숫자는 시작 U | `assetType = server` |
| `Server_U##_Face` | 서버 앞면 패널 | `M_ServerFront` 재질 사용 |
| `Anchors/Sensor_*` | 센서 위치 표시 빈 오브젝트 | 사용자 속성 `metric` (09 규격 4장) |

선택: `Door_Front`, `Door_Rear`(구멍 뚫린 문), 케이블. 문은 움직이지 않는 모양만 만든다.

## 3. 삼각형 예산

| 대상 | 목표(측정 전 가정) | 현재 |
|---|---|---|
| 랙 1기 | 15,000개 이하 | 블록아웃 312개 |
| 장면 전체(랙 20기 + 설비 + 방) | 400,000개 이하 | 미측정 |

- 목표는 **가정**이다. Unreal에서 실제 프레임 속도를 측정한 뒤(Phase 2) 조정한다.
- 확인 방법은 6장에 있다.
- 구멍이 많은 문이나 케이블이 삼각형을 많이 쓴다. 이런 부분은 **텍스처로 표현**하는 방법을 먼저 생각한다.

## 4. 모델링 순서

1. `blender/rack_blockout.blend`를 열고 **`blender/rack.blend`로 다른 이름으로 저장**한다. 프레임과 서버 10대가 있는 기준 모델이다. (블록아웃 파일은 원본으로 남겨 둔다.)
2. **크기와 원점은 바꾸지 않는다.** 세부만 더한다.
3. 프레임: 기둥에 베벨(모서리 깎기), 바닥판에 발이나 바퀴를 더한다.
4. 서버: 앞면에 손잡이, 환기구 줄, 표시등 같은 세부를 더한다. 서버 하나를 잘 만든 뒤 복사해서 쓴다. 복사할 때는 **연결 복제(Alt+D)** 로 모양 데이터를 공유하면 용량이 줄어든다.
5. 문(선택): 얇은 판에 구멍 패턴을 어레이 모디파이어로 만든다.
6. 재질: 4개(`M_RackFrame`, `M_ServerBody`, `M_ServerFront`, `M_Door`)만 쓴다. 단순한 값(색, 금속성, 거칠기)만 설정한다.
7. 6장의 점검 항목을 확인하고 내보낸다.

## 5. 해야 하는 일과 하지 않는 일

| 하는 일 | 하지 않는 일 |
|---|---|
| 모디파이어를 쓰고 **적용(Apply)** 한 뒤 내보내기 | 서브디비전 서피스 사용 |
| 스케일을 1로 맞추기 (Ctrl+A → 스케일 적용) | 조각(스컬프팅), 리깅, 애니메이션 |
| 4각형 위주로 만들기 | 5각 이상 면(n-gon)을 곡면에 쓰기 |
| 재질 칸 이름을 정해진 것만 쓰기 | 복잡한 재질 노드(절차적 텍스처 등) |
| 실제 장비가 아닌 **가상 장비**로 만들기 | 실제 제품 형상, 로고, 상표 따라 하기 |

## 6. 내보내기 전 점검표

| 번호 | 점검 | 확인 방법 |
|---|---|---|
| 1 | 모든 오브젝트의 스케일이 1이다 | 오브젝트 선택 → N 패널 → 스케일 |
| 2 | 랙의 원점이 바닥 중앙이다 | `Rack` 위치가 (0, 0, 0) |
| 3 | 크기가 60 x 100 x 200 cm 안에 있다 | 내보낸 뒤 검증 단계에서 크기 출력 |
| 4 | 면이 뒤집히지 않았다 | 오버레이 → 면 방향 → 모두 파란색 |
| 5 | 겹치는 점이 없다 | 편집 모드 → 점 선택 → 거리로 병합 |
| 6 | 이름이 규칙대로다 | 아웃라이너 확인 |
| 7 | 재질이 4개 이하이고 이름이 규칙대로다 | 재질 탭 |
| 8 | 삼각형 수가 예산 이내다 | 뷰포트 통계(오버레이 → 통계) 또는 내보낸 뒤 스크립트 출력 |
| 9 | 센서 앵커가 있고 `metric` 속성이 있다 | 아웃라이너 → 오브젝트 속성 → 사용자 속성 |
| 10 | 모디파이어를 모두 적용했다 | 수정자 탭이 비어 있거나 의도한 것만 남음 |

## 7. 내보내기와 검증

저장소 루트에서 다음 순서로 실행한다. (Blender 설치 경로가 다르면 경로를 바꾼다.)

```
# 1) Blender에서 USD로 내보내기
"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b blender\rack.blend --python blender\scripts\export_usd.py -- usd\assets\_rack_raw.usd

# 2) 규칙에 맞게 마무리 (scripts\usd_tools 폴더에서)
cd scripts\usd_tools
uv run --python 3.13 python finalize_asset.py ..\..\usd\assets\_rack_raw.usd ..\..\usd\assets\rack.usda

# 3) 검증
uv run --python 3.13 python validate_usd.py --kind asset ..\..\usd\assets\rack.usda
```
- `_rack_raw.usd`는 중간 파일이라 Git에 올리지 않는다(`.gitignore`에 이미 등록).
- 3번이 통과해야 한다. 실패하면 오류 번호와 메시지를 보고 모델을 고친다.

## 8. 시작 파일 다시 만들기

블록아웃이 망가졌거나 처음부터 다시 하고 싶으면 스크립트로 다시 만든다.
```
"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" -b --factory-startup --python blender\scripts\make_rack_blockout.py -- blender\rack_blockout.blend
```

## 9. 막혔을 때
| 증상 | 확인할 것 |
|---|---|
| 내보낸 크기가 다르다 | 스케일 적용 여부, 부모-자식 관계에서 위치가 두 번 더해지지 않았는지(블록아웃 스크립트에서 이미 한 번 겪은 문제) |
| 조명이 이상하게 어둡다 | 면 방향(법선) 확인 |
| 검증에서 `U202` | 장비 이름(`Server_U##` 등)인데 `assetType`이 없다 |
| 검증에서 `U203` | `assetType` 값이 허용 목록에 없다 |
| 재질이 회색으로 보인다 | 재질 노드를 Principled BSDF 하나로 단순화 |

## 10. 홀 외피와 둘러보기를 위한 주의 (Phase 2)

내부 둘러보기([12](12_unreal_design.md) 10장)에서는 **데이터센터 내부가 곧 장면**이라서, 방을 따로 모델링하지 않는다. 바닥, 벽, 천장은 장면 생성 스크립트가 상자로 만든다([09](09_usd_spec.md) 11장).

모델링하는 사람이 신경 쓸 점은 두 가지다.
- 랙을 눈높이에서 가까이 보므로 **서버 앞면과 문의 세부가 눈에 띈다.** 삼각형 예산 안에서 앞면 세부를 우선한다.
- 통로 폭(차가운 통로 120 cm 이상, 뜨거운 통로 100 cm 이상)은 랙의 **깊이와 배치 간격**으로 정해지므로, 랙 외형 치수(60 x 100 x 200 cm)를 바꾸면 배치 설정도 다시 확인한다.

## 11. 건물 외관 만들기 (2026-10-15 추가)

랙과 달리 건물 외관은 **스크립트 하나로 모델 전체를 다시 만든다.** 형상을 손으로 고치지 말고 `make_building_exterior.py`를 고쳐서 다시 실행한다. 규격은 [09 USD 규격](09_usd_spec.md) 12.1장.

| 순서 | 할 일 | 명령 (저장소 루트에서) |
|---|---|---|
| 0 | CC0 텍스처 내려받기(콘크리트, 아스팔트) | `uv run --python 3.13 --with numpy --with pillow python scripts/fetch_cc0_textures.py` |
| 1 | 4K 텍스처 만들기(패널, 지붕. 약 15초) | `uv run --python 3.13 --with numpy --with pillow python blender/scripts/make_building_textures.py` |
| 2 | 이음새 확인 이미지 만들기 | `uv run --python 3.13 --with numpy --with pillow python blender/scripts/check_texture_tiling.py` |
| 3 | 모델 만들기 (삼각형 수가 출력됨) | `blender -b --factory-startup --python blender/scripts/make_building_exterior.py -- blender/building_exterior.blend` |
| 4 | USD로 내보내기 (텍스처 복사 포함) | `blender -b blender/building_exterior.blend --python blender/scripts/export_usd.py -- <스크래치>/building_raw.usd --textures NEW` |
| 5 | 마무리 (`scripts/usd_tools`에서, 텍스처는 `.jpg`와 `.png`를 모두 복사한다) | `uv run --python 3.13 python finalize_asset.py <스크래치>/building_raw.usd ../../usd/assets/building.usda --textures-dir ../../usd/assets/textures/building --textures-rel textures/building` |
| 6 | 검증 | `uv run --python 3.13 python validate_usd.py --kind asset ../../usd/assets/building.usda` |
| 7 | 미리보기 렌더(검수용) | `blender -b blender/building_exterior.blend --python blender/scripts/render_building_previews.py -- blender/previews 24` |

### 저장소를 받은 뒤 텍스처 준비하기 (4K 텍스처는 저장소에 올리지 않는다)
4K 텍스처(약 250 MB)는 저장소에 올리지 않는다(`usd/assets/textures/`는 `.gitignore`에 있다). 패널과 지붕은 **생성 스크립트가 시드를 고정해 같은 결과를 만들고**, 콘크리트와 아스팔트는 **CC0 실사 텍스처(ambientCG)** 를 내려받는다. `building.usda`는 `./textures/building/*`를 상대 경로로 참조하므로 저장소를 받은 뒤 한 번 준비한다.

```
uv run --python 3.13 --with numpy --with pillow python scripts/fetch_cc0_textures.py
uv run --python 3.13 --with numpy --with pillow python blender/scripts/make_building_textures.py
New-Item -ItemType Directory -Force usd/assets/textures/building | Out-Null
Copy-Item blender/textures/building/* usd/assets/textures/building/ -Exclude *_AO.png
```
- 첫 줄: CC0 텍스처 2개를 내려받는다(약 230 MB, 라이선스와 크기는 `blender/textures/cc0_sources.json`, 출처 기록은 [ASSET_LICENSES](ASSET_LICENSES.md)).
- 둘째 줄: 패널과 지붕 4K 텍스처를 만든다(약 15초). 셋째, 넷째 줄: AO를 뺀 파일을 USD가 찾는 위치로 복사한다. AO는 USD 재질에 연결하지 않았고 Unreal에서 쓸 수 있게 남겨 둔 파일이다.
- 텍스처가 없으면 `building.usda`는 열리지만 재질이 회색으로 보인다.

### 텍스처와 형상을 맞추는 원칙 (노이즈를 막는다)
1. **중복하지 않는다.** 형상에 이미 있는 디테일(패널 틈, 루버 슬랫, 난간)을 텍스처에 또 그리지 않는다. 우리 패널은 틈을 형상으로 만들었으므로 텍스처는 이음선이 없는 평평한 면이 맞고, 골판 텍스처는 맞지 않는다.
2. **실제 크기를 맞춘다.** 텍스처의 실제 크기(아스팔트 250 cm, 콘크리트 240 cm)를 UV 타일 크기(`TS_ASPH`, `TS_CONC`)와 같게 둔다. 어긋나면 골재 알갱이가 거인이나 개미 크기로 보인다.
3. **큰 것은 형상, 작은 것은 텍스처.** 베벨, 틈, 슬랫은 형상이고 질감, 얼룩은 텍스처다.
4. **노멀의 세기를 제한한다.** 노멀 맵의 평균 기울기가 0.3을 넘으면 먼 거리에서 반짝이는 노이즈가 된다(2026-10-15: 절차 아스팔트 0.62, 콘크리트 0.34로 측정). CC0 아스팔트는 0.40이라 0.6배로 줄여 0.24로 썼다(`cc0_sources.json`의 `normal_strength`).
5. **같은 평면에 면을 겹치지 않는다.** 같은 방향의 면이 같은 평면(0.5 cm 이내)에 겹치면 서로 깜빡이는 노이즈(z-파이팅)가 된다. 예: 벽 속 면(`WallCore`)이 난간 높이까지 올라가 패널 안쪽 면과 겹쳤다. 다음 검사로 찾는다.
```
cd scripts/usd_tools
uv run --python 3.13 python check_coplanar_faces.py ../../usd/assets/building.usda --z-min 1380
```
   - 맞붙은 반대 방향 면(패널 뒷면과 벽 앞면)은 단면 렌더에서 보이지 않아 세지 않는다. 모든 메시는 단면(`doubleSided=False`)으로 내보내고 유리(`Entrance`)만 양면이다.
   - 삼각형 부채꼴 면은 오탐이라 제외한다.

- 길이는 스크립트 안에서 **미터**로 쓰고, 만들 때 100배(cm)한다.
- 삼각형 예산: 건물 전체 200만 이하(Nanite 사용 전제). 2026-10-15 기준 약 13.8만.
- 7번 렌더는 Blender 안에서 **상대 경로**로 저장하면 드라이브 루트(`C:\blender\...`)에 써 버리므로 스크립트가 절대 경로로 바꾼다.
