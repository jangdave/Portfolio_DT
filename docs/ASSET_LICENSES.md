# 외부 에셋 출처/라이선스

직접 제작하지 않은 에셋(텍스처, HDRI, 폰트 등)은 아래에 기록한다.

| 에셋 | 출처 URL | 라이선스 | 사용 위치 |
|---|---|---|---|

## 직접 제작한 에셋 (외부 출처 없음)

외부에서 내려받은 이미지, 텍스처, 모델은 쓰지 않았다. 아래는 모두 이 저장소의 스크립트로 만든 것이다.

| 에셋 | 만든 방법 | 라이선스 | 사용 위치 |
|---|---|---|---|
| 건물 외관 4K 텍스처 14개 (`T_BldgPanelMetal_*`, `T_BldgConcrete_*`, `T_BldgRoof_*`, `T_Asphalt_*`, 각 4096x4096 PNG) | **직접 제작, 절차적 생성.** `blender/scripts/make_building_textures.py`가 numpy의 푸리에 변환 잡음(이음새 없이 이어지는 주기적 잡음)과 수식으로 색, 높이, 거칠기, 금속성을 계산하고 Pillow로 PNG로 저장한다. 사진이나 외부 이미지를 쓰지 않았다. 시드가 고정되어 같은 결과가 다시 만들어진다. | 이 저장소의 라이선스를 따른다 (직접 제작) | `usd/assets/building.usda` |
| 건물 외관 3D 모델 (`blender/building_exterior.blend`, `usd/assets/building.usda`) | **직접 제작.** `blender/scripts/make_building_exterior.py`가 Blender로 형상을 만든다. 가상 시설이며 실제 시설의 형상, 도면, 로고, 상표를 따라 하지 않았다. 레퍼런스는 공통 특징만 참고했다([15](15_exterior_references.md)). | 이 저장소의 라이선스를 따른다 (직접 제작) | 외관 화면 |
