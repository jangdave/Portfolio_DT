# DC-Twin 환경 점검. 읽기 전용: 아무것도 설치/변경하지 않는다.
# 사용: .\scripts\check_env.ps1 [-OvLibsVenv <ovrtx가 설치된 venv 경로>] [-KitTemplate <Kit 앱 템플릿 경로>]
param(
    [string]$OvLibsVenv = 'D:\omniverse-labs-main\samples\ovrtx_ovphysx_livestream\livestream-files\examples\python\ov-libaries-livestream\.venv',
    [string]$KitTemplate = 'D:\omniverse-kit\kit-app-template'
)

$results = @()
function Add-Check($name, $ok, $detail) {
    $script:results += [pscustomobject]@{ Check = $name; Status = $(if ($ok) { 'OK' } else { 'MISSING' }); Detail = $detail }
}

# GPU
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($smi) {
    $gpu = & nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
    Add-Check 'GPU' $true $gpu
} else { Add-Check 'GPU' $false 'nvidia-smi 없음' }

# Unreal 5.8 (주 사용)
$ue = 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
Add-Check 'Unreal 5.8' (Test-Path $ue) $ue

# Blender
$bl = Get-ChildItem 'C:\Program Files\Blender Foundation' -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
Add-Check 'Blender' ([bool]$bl) $(if ($bl) { $bl.Name } else { '없음' })

# CLI tools
foreach ($c in 'git', 'node', 'uv', 'wsl', 'mosquitto', 'docker') {
    $r = Get-Command $c -ErrorAction SilentlyContinue
    Add-Check $c ([bool]$r) $(if ($r) { $r[0].Source } else { '없음' })
}

# Omniverse Libraries (ovrtx / ovphysx)
$py = Join-Path $OvLibsVenv 'Scripts\python.exe'
if (Test-Path $py) {
    $ver = & $py -I -c "import importlib.metadata as m; print('ovrtx', m.version('ovrtx'), '| ovphysx', m.version('ovphysx'))" 2>$null
    Add-Check 'Omniverse Libraries' ([bool]$ver) $ver
} else { Add-Check 'Omniverse Libraries' $false "venv 없음: $OvLibsVenv" }

# Omniverse Kit 앱: 우리가 빌드한 앱(kit-app-template의 dctwin.base_editor)을 먼저 보고, 없으면 Launcher 설치 위치(%LOCALAPPDATA%\ov\pkg)를 본다
$kitApp = Join-Path $KitTemplate 'source\apps\dctwin.base_editor.kit'
# 빌드 결과의 실행 파일은 kit.bat이다(kit.exe는 packman 저장소에 있고 _build에는 연결만 있다)
$kitExe = Get-ChildItem (Join-Path $KitTemplate '_build') -Recurse -Depth 4 -Filter kit.bat -ErrorAction SilentlyContinue | Select-Object -First 1
if ((Test-Path $kitApp) -and $kitExe) {
    Add-Check 'Omniverse Kit app' $true "dctwin.base_editor (빌드됨): $($kitExe.FullName)"
} else {
    $kit = Get-ChildItem "$env:LOCALAPPDATA\ov\pkg" -Recurse -Depth 3 -Filter kit.exe -ErrorAction SilentlyContinue | Select-Object -First 1
    Add-Check 'Omniverse Kit app' ([bool]$kit) $(if ($kit) { $kit.FullName } else { "없음 (확인한 곳: $KitTemplate)" })
}

$results | Format-Table -AutoSize -Wrap
