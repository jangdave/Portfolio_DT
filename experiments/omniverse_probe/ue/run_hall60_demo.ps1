# 랙 60기 홀 시뮬레이션 결과(VDB 시퀀스)를 별도 UE 프로젝트의 레벨 3개로 만든다. (저장소 루트에서 실행)
# 레벨 3개는 데이터가 같고 축 방향만 다르다(원본, X 뒤집기, Y 뒤집기). 어느 쪽이 장비 위치와 맞는지 눈으로 확인한다.
# 엔진 버전은 -Engine으로 지정한다(기본 5.8). 별도 프로젝트 폴더를 쓰므로 다른 에디터가 열려 있어도 충돌하지 않는다.
param(
    [string]$Engine = "C:\Program Files\Epic Games\UE_5.8",
    [string]$EngineAssociation = "5.8",
    [string]$Project = "D:\ue_probe\Hall60Demo",
    [string]$Frames = "D:\Test\experiments\omniverse_probe\out\hall60\frames",
    [string]$Layout = "D:\Test\experiments\omniverse_probe\out\hall60\layout.json",
    [string]$Failed = "CRAC_02,CRAC_06",
    [string]$Result = "D:\ue_probe\hall60_result.json",
    [string]$Log = "D:\ue_probe\hall60_run.log",
    [int]$TimeoutSec = 400
)
$ue = Join-Path $Engine "Engine\Binaries\Win64\UnrealEditor.exe"
$script = (Resolve-Path "experiments\omniverse_probe\ue\build_heat_demo.py").Path.Replace("\", "/")
$files = "$Frames\vdb_norm_seq\TempN_000.vdb;$Frames\vdb_norm_flipx_seq\TempFX_000.vdb;$Frames\vdb_norm_flipy_seq\TempFY_000.vdb"
New-Item -ItemType Directory -Force "$Project\Config" | Out-Null
$uproject = @"
{
	"FileVersion": 3,
	"EngineAssociation": "$EngineAssociation",
	"Description": "랙 60기 홀 열 시뮬레이션 볼륨 데모 (저장소에 올리지 않는다)",
	"Plugins": [
		{ "Name": "Interchange", "Enabled": true },
		{ "Name": "InterchangeEditor", "Enabled": true },
		{ "Name": "InterchangeOpenVDB", "Enabled": true },
		{ "Name": "PythonScriptPlugin", "Enabled": true },
		{ "Name": "EditorScriptingUtilities", "Enabled": true }
	]
}
"@
$name = Split-Path $Project -Leaf
Set-Content -Path "$Project\$name.uproject" -Value $uproject -Encoding UTF8
$ini = "$Project\Config\DefaultEngine.ini"
Set-Content -Path $ini -Encoding UTF8 -Value "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]`n+StartupScripts=$script"
Remove-Item $Result, $Log -ErrorAction SilentlyContinue
# 환경 변수로 전달한다(자식 프로세스가 물려받음). cmd 인용 문제를 피하려고 직접 실행한다.
$env:DCT_VDB_FILES = $files
$env:DCT_LAYOUT = $Layout.Replace("\", "/")
$env:DCT_UE_RESULT = $Result.Replace("\", "/")
$env:DCT_TMIN = "15"; $env:DCT_TMAX = "45"; $env:DCT_TWARN = "27"; $env:DCT_TCRIT = "32"  # 저장 범위 15~45도, 주의 27도, 위험 32도
$env:DCT_DENSITY = "0.01"; $env:DCT_PKG = "Hall60"; $env:DCT_FAILED = $Failed
$p = Start-Process -FilePath $ue -ArgumentList "$Project\$name.uproject", "-nosplash", "-nopause", "-NoSound", "-RenderOffScreen", "-abslog=$Log" -PassThru -WindowStyle Hidden
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec -and -not $p.HasExited) { Start-Sleep -Seconds 3 }
# 시작 스크립트 설정은 반드시 제거한다(남아 있으면 에디터를 열 때마다 스크립트가 다시 실행되고 종료된다)
Remove-Item $ini -Force -ErrorAction SilentlyContinue
"wall: $([math]::Round($sw.Elapsed.TotalSeconds,1))s | exited: $($p.HasExited) | exit code: $(if ($p.HasExited) { $p.ExitCode }) | startup-setting-removed: $(-not (Test-Path $ini))"
