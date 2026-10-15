# UE 5.7 에디터를 명령줄로 실행해 시험 스크립트를 돌린다. (저장소 루트에서 실행)
# 사용 예:
#   .\experiments\omniverse_probe\ue\run_import_probe.ps1 -Files "a.vdb;b.vdb"
#   .\experiments\omniverse_probe\ue\run_import_probe.ps1 -Script "experiments\omniverse_probe\ue\discover_volume_classes.py" -Result "D:\ue_probe\discover.json"
param(
    [string]$Files = "",
    [string]$Script = "experiments\omniverse_probe\ue\import_vdb_probe.py",
    [string]$Project = "D:\ue_probe\VdbProbe\VdbProbe.uproject",
    [string]$Result = "D:\ue_probe\vdb_import_result.json",
    [string]$Exe = "UnrealEditor-Cmd.exe",   # 화면을 그려야 하면 UnrealEditor.exe (스크립트가 끝나도 종료하지 않는다)
    [int]$TimeoutSec = 540
)
$ue = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\$Exe"
$log = Join-Path (Split-Path $Result) "ue_run.log"
Remove-Item $log, $Result -ErrorAction SilentlyContinue
$scriptPath = (Resolve-Path $Script).Path.Replace("\", "/")
$resultFwd = $Result.Replace("\", "/")
$cmd = "set DCT_VDB_FILES=$Files&& set DCT_UE_RESULT=$resultFwd&& `"$ue`" `"$Project`" -ExecutePythonScript=`"$scriptPath`" -unattended -nosplash -nopause -NoSound -RenderOffScreen -abslog=`"$log`""
$p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -PassThru -WindowStyle Hidden
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    Start-Sleep -Seconds 6
    if (Test-Path $Result) { Start-Sleep -Seconds 5; break }
    if ($p.HasExited) { break }
}
"wall: $([math]::Round($sw.Elapsed.TotalSeconds,1))s | result: $(Test-Path $Result) | exited: $($p.HasExited)"
