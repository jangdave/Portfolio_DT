# UE 5.8에서 홀 장면(USD) 가져오기를 시험한다. (저장소 루트에서 실행)
# 시험용 임시 프로젝트를 -Work 폴더에 만들고, 끝나면 지운다(저장소와 사용자 프로젝트를 건드리지 않는다).
param(
    [string]$Engine = "C:\Program Files\Epic Games\UE_5.8",
    [string]$Work = "$env:TEMP\dct_usd_probe",
    [string]$Usd = "D:\Test\usd\scenes\hall01.usda",
    [string]$Result = "D:\Test\experiments\omniverse_probe\out\ue58_usd_probe.json",
    [string]$Log = "$env:TEMP\dct_usd_probe.log",
    [int]$TimeoutSec = 300,
    [switch]$Keep
)
$ue = Join-Path $Engine "Engine\Binaries\Win64\UnrealEditor.exe"
$script = (Resolve-Path "experiments\omniverse_probe\ue\probe_usd_import.py").Path
if (Test-Path $Work) { Remove-Item -Recurse -Force $Work }
New-Item -ItemType Directory -Force "$Work\Config" | Out-Null
$uproject = @"
{
	"FileVersion": 3,
	"EngineAssociation": "5.8",
	"Description": "USD 가져오기 시험 (임시)",
	"Plugins": [
		{ "Name": "Interchange", "Enabled": true },
		{ "Name": "InterchangeEditor", "Enabled": true },
		{ "Name": "InterchangeOpenVDB", "Enabled": true },
		{ "Name": "InterchangeOpenUSD", "Enabled": true },
		{ "Name": "USDImporter", "Enabled": true },
		{ "Name": "PythonScriptPlugin", "Enabled": true },
		{ "Name": "EditorScriptingUtilities", "Enabled": true }
	]
}
"@
Set-Content -Path "$Work\Probe.uproject" -Value $uproject -Encoding UTF8
Set-Content -Path "$Work\Config\DefaultEngine.ini" -Encoding UTF8 -Value "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]`n+StartupScripts=$($script.Replace('\', '/'))"
Remove-Item $Result, $Log -ErrorAction SilentlyContinue
$env:DCT_USD = $Usd.Replace("\", "/")
$env:DCT_UE_RESULT = $Result.Replace("\", "/")
$p = Start-Process -FilePath $ue -ArgumentList "$Work\Probe.uproject", "-nosplash", "-nopause", "-NoSound", "-RenderOffScreen", "-abslog=`"$Log`"" -PassThru -WindowStyle Hidden
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec -and -not $p.HasExited) { Start-Sleep -Seconds 3 }
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
"wall: $([math]::Round($sw.Elapsed.TotalSeconds,1))s | exit code: $(if ($p.HasExited) { $p.ExitCode }) | result: $(Test-Path $Result) | log: $Log"
if (-not $Keep) { Remove-Item -Recurse -Force $Work -ErrorAction SilentlyContinue }
