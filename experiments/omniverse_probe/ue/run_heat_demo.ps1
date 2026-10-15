# 전용 볼륨 머티리얼 데모(build_heat_demo.py)를 별도 UE 프로젝트에 만든다. (저장소 루트에서 실행)
# 별도 프로젝트 폴더를 쓰므로, 다른 에디터가 열려 있어도 충돌하지 않는다.
param(
    [string]$Project = "D:\ue_probe\HeatDemo3",
    [string]$Frames = "D:\Test\experiments\omniverse_probe\out\frames",
    [string]$Layout = "D:\Test\experiments\omniverse_probe\out\layout.json",
    [int]$TimeoutSec = 300
)
$ue = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"
$script = (Resolve-Path "experiments\omniverse_probe\ue\build_heat_demo.py").Path.Replace("\", "/")
# 원본, X 뒤집기, Y 뒤집기 시퀀스의 첫 파일
$files = "$Frames\vdb_norm_seq\TempN_000.vdb;$Frames\vdb_norm_flipx_seq\TempFX_000.vdb;$Frames\vdb_norm_flipy_seq\TempFY_000.vdb"
New-Item -ItemType Directory -Force "$Project\Config" | Out-Null
$uproject = @'
{
	"FileVersion": 3,
	"EngineAssociation": "5.7",
	"Description": "열 시뮬레이션 볼륨 데모 (저장소에 올리지 않는다)",
	"Plugins": [
		{ "Name": "Interchange", "Enabled": true },
		{ "Name": "InterchangeEditor", "Enabled": true },
		{ "Name": "InterchangeOpenVDB", "Enabled": true },
		{ "Name": "PythonScriptPlugin", "Enabled": true },
		{ "Name": "EditorScriptingUtilities", "Enabled": true }
	]
}
'@
Set-Content -Path "$Project\HeatDemo.uproject" -Value $uproject -Encoding UTF8
$ini = "$Project\Config\DefaultEngine.ini"
Set-Content -Path $ini -Encoding UTF8 -Value "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]`n+StartupScripts=$script"
$result = "D:\ue_probe\heat_result.json"
$log = "D:\ue_probe\heat_run.log"
Remove-Item $result, $log -ErrorAction SilentlyContinue
$cmd = "set DCT_VDB_FILES=$files&& set DCT_LAYOUT=$($Layout.Replace('\','/'))&& set DCT_UE_RESULT=$($result.Replace('\','/'))&& `"$ue`" `"$Project\HeatDemo.uproject`" -nosplash -nopause -NoSound -RenderOffScreen -abslog=`"$log`""
$p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", $cmd -PassThru -WindowStyle Hidden
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) { Start-Sleep -Seconds 5; if (Test-Path $result) { Start-Sleep -Seconds 8; break } }
# 시작 스크립트 설정은 반드시 제거한다(남아 있으면 에디터를 열 때마다 스크립트가 다시 실행되고 종료된다)
Start-Sleep -Seconds 3
Remove-Item $ini -Force -ErrorAction SilentlyContinue
"wall: $([math]::Round($sw.Elapsed.TotalSeconds,1))s | result: $(Test-Path $result) | startup-setting-removed: $(-not (Test-Path $ini))"
