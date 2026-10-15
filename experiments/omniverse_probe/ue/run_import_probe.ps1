# UE 5.7 에디터를 명령줄로 실행해 VDB 가져오기 시험 스크립트를 돌린다. (저장소 루트에서 실행)
param([string]$Files, [string]$Project = "D:\ue_probe\VdbProbe\VdbProbe.uproject", [string]$Result = "D:\ue_probe\vdb_import_result.json", [int]$TimeoutSec = 540)
$ue = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$log = Join-Path (Split-Path $Result) "ue_vdb_import.log"
Remove-Item $log, $Result -ErrorAction SilentlyContinue
$script = (Resolve-Path "experiments\omniverse_probe\ue\import_vdb_probe.py").Path.Replace("\", "/")
$cmd = "set DCT_VDB_FILES=$Files&& set DCT_UE_RESULT=$($Result.Replace('\','/'))&& `"$ue`" `"$Project`" -ExecutePythonScript=`"$script`" -unattended -nosplash -nopause -NoSound -RenderOffScreen -abslog=`"$log`""
$p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -PassThru -WindowStyle Hidden
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) { Start-Sleep -Seconds 6; if (Test-Path $Result) { Start-Sleep -Seconds 5; break }; if ($p.HasExited) { break } }
"wall: $([math]::Round($sw.Elapsed.TotalSeconds,1))s | result: $(Test-Path $Result) | exited: $($p.HasExited)"
