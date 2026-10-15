# DC-Twin 환경 점검. 읽기 전용: 아무것도 설치/변경하지 않는다.
# 사용: .\scripts\check_env.ps1 [-OvLibsVenv <ovrtx가 설치된 venv 경로>]
param(
    [string]$OvLibsVenv = 'D:\omniverse-labs-main\samples\ovrtx_ovphysx_livestream\livestream-files\examples\python\ov-libaries-livestream\.venv'
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

# Unreal 5.7
$ue = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
Add-Check 'Unreal 5.7' (Test-Path $ue) $ue

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

# Omniverse Kit apps (kit.exe) - 알려진 위치만 확인
$kit = Get-ChildItem "$env:LOCALAPPDATA\ov\pkg" -Recurse -Depth 3 -Filter kit.exe -ErrorAction SilentlyContinue | Select-Object -First 1
Add-Check 'Omniverse Kit app' ([bool]$kit) $(if ($kit) { $kit.FullName } else { '미설치 (Libraries 경로 사용)' })

$results | Format-Table -AutoSize -Wrap
