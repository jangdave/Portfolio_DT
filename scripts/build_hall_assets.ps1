# 서버 홀 에셋(랙, CRAC)을 처음부터 다시 만든다: Blender 모델 -> USD 내보내기 -> 규칙에 맞게 마무리 -> 검증.
# 사용 (저장소 루트에서):  powershell -File scripts/build_hall_assets.ps1
# 먼저 텍스처가 있어야 한다(docs/10_modeling_guide.md 12장): fetch_cc0_textures.py, make_hall_textures.py
param(
    [string]$Blender = "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    [string]$Scratch = "$env:TEMP\dct_hall_raw"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force $Scratch | Out-Null
New-Item -ItemType Directory -Force usd/assets/textures/hall | Out-Null

foreach ($a in @(@{n = "rack"; s = "make_rack_detailed.py"}, @{n = "crac"; s = "make_crac_detailed.py"})) {
    & $Blender -b --factory-startup --python "blender/scripts/$($a.s)" -- "blender/$($a.n).blend" | Select-String "삼각형 합계|경계 상자|Blender가 센"
    & $Blender -b "blender/$($a.n).blend" --python blender/scripts/export_usd.py -- "$Scratch/$($a.n)_raw.usd" --textures NEW | Out-Null
    Push-Location scripts/usd_tools
    uv run --python 3.13 python finalize_asset.py "$Scratch/$($a.n)_raw.usd" "../../usd/assets/$($a.n).usda" --textures-dir ../../usd/assets/textures/hall --textures-rel textures/hall
    uv run --python 3.13 python validate_usd.py --kind asset "../../usd/assets/$($a.n).usda"
    Pop-Location
}
# 장면에서 쓰는 텍스처(CC0, 절차 생성)를 USD가 찾는 위치로 복사한다. AO는 USD 재질에 연결하지 않으므로 제외한다.
Copy-Item blender/textures/hall/* usd/assets/textures/hall/ -Exclude *_AO.png
