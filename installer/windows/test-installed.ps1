param([switch]$RestartService)
$ErrorActionPreference='Stop'
$service=Get-CimInstance Win32_Service -Filter "Name='BuildCostIQProjectServer'"
if (!$service -or $service.StartMode -ne 'Auto' -or $service.State -ne 'Running') { throw 'Service must exist, be Automatic and Running' }
if ($service.StartName -ne 'NT AUTHORITY\LocalService') { throw 'Unexpected service identity' }
$configFile=Join-Path $env:ProgramData 'BuildCostIQ\server.json'
$config=Get-Content $configFile -Raw | ConvertFrom-Json
if ($config.PSObject.Properties.Name -contains 'password') { throw 'Plaintext password present in configuration' }
$data=[IO.Path]::GetFullPath($config.data_root)
$backup=[IO.Path]::GetFullPath($config.backup_root)
if ($data -eq $backup -or $data.StartsWith($backup+'\',[StringComparison]::OrdinalIgnoreCase) -or $backup.StartsWith($data+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Data and backup not independent' }
$project=Join-Path $data ('projects\'+$config.project_code+'.json')
$users=Join-Path $data 'auth\users.json'
foreach ($path in @($project,$users,$backup)) { if(!(Test-Path -LiteralPath $path)){throw 'Required installed storage missing'} }
$beforeProject=(Get-FileHash -LiteralPath $project).Hash
$beforeUsers=(Get-FileHash -LiteralPath $users).Hash
if ($RestartService) {
    Restart-Service BuildCostIQProjectServer
    (Get-Service BuildCostIQProjectServer).WaitForStatus('Running',[TimeSpan]::FromSeconds(30))
}
$health=$null
for($attempt=0;$attempt -lt 30;$attempt++) {
    try { $health=Invoke-RestMethod 'http://127.0.0.1:8787/api/health' -TimeoutSec 2; break } catch { Start-Sleep -Seconds 1 }
}
if (!$health -or $health.runtime.version -ne '0.8.0-rc9' -or $health.deployment.mode -ne 'central') { throw 'Installed rc9 API health failed' }
if ((Get-FileHash -LiteralPath $project).Hash -ne $beforeProject -or (Get-FileHash -LiteralPath $users).Hash -ne $beforeUsers) { throw 'Verification/restart changed project or users' }
@{status='passed';service='Automatic/Running';version=$health.runtime.version;restart_checked=[bool]$RestartService;project_and_users_retained=$true} | ConvertTo-Json
