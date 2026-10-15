# 외부 에셋 출처/라이선스

직접 제작하지 않은 에셋(텍스처, HDRI, 폰트 등)은 아래에 기록한다.

| 에셋 | 출처 URL | 라이선스 | 사용 위치 |
|---|---|---|---|
| **Asphalt033** (ambientCG, 4K-JPG: 색, 노멀 GL, 거칠기. 노멀 기울기를 0.6배로 줄여 저장) | https://ambientcg.com/a/Asphalt033 (압축 파일 SHA-256 `a7fbd2e2e8016716d37d03532ccf4e52b93cff338f0f6db5f3e54a0dbcf0489f`) | CC0 1.0 Universal (https://docs.ambientcg.com/license/ 에서 2026-10-15 확인). 출처 표기는 필수가 아니지만 권장됨: "Created using Asphalt033 from ambientCG.com, licensed under the Creative Commons CC0 1.0 Universal" | 건물 외관의 부지 바닥(`T_Asphalt_*`) |
| **Concrete046** (ambientCG, 4K-JPG: 색, 노멀 GL, 거칠기) | https://ambientcg.com/a/Concrete046 (압축 파일 SHA-256 `ca5757af54176e96add5a5440efd9672885d6dee271070ccef496e64c3a9ce93`) | CC0 1.0 Universal (위와 같음). Created using Concrete046 from ambientCG.com, licensed under the Creative Commons CC0 1.0 Universal | 건물 외관의 기초, 포장, 설비 받침(`T_BldgConcrete_*`) |

- 위 두 개는 **저장소에 올리지 않는다.** `scripts/fetch_cc0_textures.py`가 ambientCG에서 내려받아 `blender/textures/building/`에 놓는다(목록: `blender/textures/cc0_sources.json`). 실제 크기는 아스팔트 250 cm, 콘크리트 240 cm이며 `make_building_exterior.py`의 타일 크기와 같다.

## 직접 제작한 에셋 (외부 출처 없음)

외부에서 내려받은 이미지, 텍스처, 모델은 쓰지 않았다. 아래는 모두 이 저장소의 스크립트로 만든 것이다.

| 에셋 | 만든 방법 | 라이선스 | 사용 위치 |
|---|---|---|---|
| 건물 외관 4K 텍스처 (패널 `T_BldgPanelMetal_*`, 지붕 `T_BldgRoof_*`, 각 4096x4096 PNG. 콘크리트와 아스팔트는 위 CC0 텍스처로 바꿨고, 절차 생성 버전은 `--only concrete,asphalt`로 만들 수 있는 대체용) | **직접 제작, 절차적 생성.** `blender/scripts/make_building_textures.py`가 numpy의 푸리에 변환 잡음(이음새 없이 이어지는 주기적 잡음)과 수식으로 색, 높이, 거칠기, 금속성을 계산하고 Pillow로 PNG로 저장한다. 사진이나 외부 이미지를 쓰지 않았다. 시드가 고정되어 같은 결과가 다시 만들어진다. | 이 저장소의 라이선스를 따른다 (직접 제작) | `usd/assets/building.usda` |
| 건물 외관 3D 모델 (`blender/building_exterior.blend`, `usd/assets/building.usda`) | **직접 제작.** `blender/scripts/make_building_exterior.py`가 Blender로 형상을 만든다. 가상 시설이며 실제 시설의 형상, 도면, 로고, 상표를 따라 하지 않았다. 레퍼런스는 공통 특징만 참고했다([15](15_exterior_references.md)). | 이 저장소의 라이선스를 따른다 (직접 제작) | 외관 화면 |
