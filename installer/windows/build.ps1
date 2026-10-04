param([string]$Compiler, [string]$OutputDir = "$PSScriptRoot\..\..\dist\windows", [string]$BuildDir, [switch]$Resume)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path "$PSScriptRoot\..\..").Path
if (!$BuildDir) { $BuildDir = Join-Path $repo 'work\windows-build' }
$build = [IO.Path]::GetFullPath($BuildDir)
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
$payload = Join-Path $build 'payload'
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (!$Compiler) { $Compiler = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' }
if (!(Test-Path $Compiler)) { $Compiler = Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe' }
if (!(Test-Path $Compiler)) { throw 'Inno Setup compiler missing; existing payload retained. Supply -Compiler before resuming.' }
if (!(Test-Path $python)) { throw 'Build Python missing' }
New-Item -ItemType Directory -Force $payload,$OutputDir | Out-Null
if ((Test-Path "$payload\runtime") -and !$Resume) { throw 'Build payload already exists. Use -Resume after a tooling interruption or a fresh work/windows-build directory.' }
if (!(Test-Path "$payload\runtime")) {
Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' -OutFile "$build\python.zip"
Expand-Archive "$build\python.zip" "$payload\runtime"
}
@('python312.zip','.','Lib/site-packages','../app','..','import site') | Set-Content "$payload\runtime\python312._pth" -Encoding ascii
if (!(Test-Path "$build\dependencies.complete")) {
if (Test-Path "$payload\runtime\Lib\site-packages") {
    throw 'Dependency directory has no completion receipt. Verify it or build in a fresh directory; refusing partial reuse.'
}
& $python -m pip install --target "$payload\runtime\Lib\site-packages" 'openpyxl>=3.1' 'pypdf>=5.0' 'markitdown[pdf,docx,xlsx]>=0.1.7' tzdata
if ($LASTEXITCODE) { throw 'Dependency packaging failed' }
Set-Content "$build\dependencies.complete" 'pip completed successfully' -Encoding ascii
}
New-Item -ItemType Directory -Force "$payload\app" | Out-Null
foreach ($name in @('core','plugins','adapters','gui','domains')) {
    New-Item -ItemType Directory -Force "$payload\app\$name" | Out-Null
    $sourceRoot = (Resolve-Path "$repo\$name").Path
    Get-ChildItem $sourceRoot -File -Recurse | Where-Object {
        $_.Extension -in @('.py','.html','.css','.js','.png','.ico') -and $_.FullName -notmatch '[\\/]buildcostiq-codex[\\/]'
    } | ForEach-Object {
        $relative = $_.FullName.Substring($sourceRoot.Length+1)
        $target = Join-Path "$payload\app\$name" $relative
        New-Item -ItemType Directory -Force (Split-Path $target) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $target -Force
    }
    Get-ChildItem "$payload\app\$name" -Directory -Recurse -Filter __pycache__ | Remove-Item -Recurse -Force
}
$excludedPlugin = [IO.Path]::GetFullPath((Join-Path $payload 'app\plugins\buildcostiq-codex'))
if (!$excludedPlugin.StartsWith([IO.Path]::GetFullPath($payload) + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid staging cleanup path' }
if (Test-Path -LiteralPath $excludedPlugin) {
    $quarantine = Join-Path $build ('excluded-plugin-' + [guid]::NewGuid().ToString('N'))
    Move-Item -LiteralPath $excludedPlugin -Destination $quarantine
}
Copy-Item "$PSScriptRoot\launch.py","$PSScriptRoot\initialize.py","$PSScriptRoot\configure.ps1" $payload
Copy-Item "$repo\LICENSE" "$payload\LICENSE.txt"
New-Item -ItemType Directory -Force "$payload\licenses" | Out-Null
Copy-Item "$PSScriptRoot\languages\ChineseSimplified-MIT-LICENSE.txt" "$payload\licenses\Inno-Setup-Chinese-Simplified-Translation-LICENSE.txt"
Copy-Item "$repo\pyproject.toml" "$payload\app\pyproject.toml"
if (!(Test-Path "$payload\BuildCostIQService.exe")) {
Invoke-WebRequest 'https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe' -OutFile "$payload\BuildCostIQService.exe"
}
$probe = Join-Path $build 'runtime-import-probe.py'
@'
import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as scratch:
    os.environ["BUILDCOSTIQ_DATA_ROOT"] = str(Path(scratch) / "Data")
    import openpyxl, pypdf, markitdown, gui.server
    from domains.business_workflows import definitions
    from core.version import current_version
    assert current_version() == "0.8.0-rc9" and len(definitions()) == 8
    print("imports OK: rc9; 8 business workflow modules")
'@ | Set-Content -LiteralPath $probe -Encoding utf8
& "$payload\runtime\python.exe" -B $probe
$probeExit = $LASTEXITCODE
Remove-Item -LiteralPath $probe -Force
if ($probeExit) { throw 'Embedded runtime import failed' }
& $python -B "$PSScriptRoot\smoke.py" $payload $OutputDir
if ($LASTEXITCODE) { throw 'Payload smoke test failed' }
# Embedded distribution intentionally contains no pip; freeze with build Python instead.
& $python -m pip list --path "$payload\runtime\Lib\site-packages" --format=freeze | Set-Content "$OutputDir\dependencies.lock.txt"
& $python -B "$PSScriptRoot\delivery_check.py" verify $payload $OutputDir
if ($LASTEXITCODE) { throw 'Payload verification failed' }
& $Compiler "/DPayload=$payload" "/DOutputDir=$OutputDir" "/DInstallerLanguages=$PSScriptRoot\languages" "$PSScriptRoot\project-server.iss"
if ($LASTEXITCODE) { throw 'Installer compilation failed' }
& $python -B "$PSScriptRoot\delivery_check.py" installer $payload $OutputDir
if ($LASTEXITCODE) { throw 'Installer receipt failed' }
