# UE 데모 레벨을 변형(투명도, 발광, 태양 세기)별로 만들고 화면을 캡처한다. (저장소 루트에서 실행)
# 사용: .\experiments\omniverse_probe\ue\run_demo_variant.ps1 -Tag a -Extinction 0.0005 -Emissive 0 -Sun 10
# 프로젝트의 시작 스크립트 설정(Config\DefaultEngine.ini)으로 build_volume_demo.py를 실행하므로 에디터가 종료되지 않고 화면을 캡처할 수 있다.
param(
    [string]$Tag = "a",
    [double]$Extinction = 0.0005,
    [int]$Emissive = 0,
    [double]$Sun = 10,
    [string]$Project = "D:\ue_probe\VdbProbe",
    [string]$FirstVdb = "D:\Test\experiments\omniverse_probe\out\frames\vdb_seq\Temp_000.vdb",
    [int]$TimeoutSec = 240
)
$ue = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"
$script = (Resolve-Path "experiments\omniverse_probe\ue\build_volume_demo.py").Path.Replace("\", "/")
New-Item -ItemType Directory -Force "$Project\Config" | Out-Null
Set-Content -Path "$Project\Config\DefaultEngine.ini" -Encoding UTF8 -Value "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]`n+StartupScripts=$script"
$result = "D:\ue_probe\demo_$Tag.json"
$log = "D:\ue_probe\demo_$Tag.log"
Remove-Item $result, $log -ErrorAction SilentlyContinue
Remove-Item "$Project\Saved\Screenshots" -Recurse -ErrorAction SilentlyContinue
$cmd = "set DCT_VDB_FILES=$FirstVdb&& set DCT_UE_RESULT=$($result.Replace('\','/'))&& set DCT_EXTINCTION=$Extinction&& set DCT_EMISSIVE=$Emissive&& set DCT_SUN=$Sun&& set DCT_SHOT_TAG=demo_$Tag&& `"$ue`" `"$Project\VdbProbe.uproject`" -nosplash -nopause -NoSound -RenderOffScreen -abslog=`"$log`""
$p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -PassThru -WindowStyle Hidden
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    Start-Sleep -Seconds 5
    if (Test-Path $result) { Start-Sleep -Seconds 6; break }
}
if (-not (Test-Path $result)) { Get-Process UnrealEditor -ErrorAction SilentlyContinue | Stop-Process -Force }
$shots = Get-ChildItem "$Project\Saved\Screenshots" -Recurse -Filter "demo_$Tag*.png" -ErrorAction SilentlyContinue
"wall: $([math]::Round($sw.Elapsed.TotalSeconds,1))s | result: $(Test-Path $result) | screenshots: $(@($shots).Count)"
$shots | ForEach-Object { $_.FullName }
