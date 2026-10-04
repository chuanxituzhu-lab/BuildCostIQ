param([string]$InstallDir, [switch]$Remove)
$ErrorActionPreference = 'Stop'
$configRoot = Join-Path $env:ProgramData 'BuildCostIQ'
$configFile = Join-Path $configRoot 'server.json'
$service = Join-Path $InstallDir 'BuildCostIQService.exe'
if ($Remove) {
    if (Get-Service BuildCostIQProjectServer -ErrorAction SilentlyContinue) {
        & $service stop
        if ($LASTEXITCODE) { throw 'Service stop failed; program and data must be retained' }
        & $service uninstall
        if ($LASTEXITCODE) { throw 'Service removal failed' }
    }
    Get-NetFirewallRule -DisplayName 'BuildCostIQ Project Server' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    exit 0
}
$logs = Join-Path $configRoot 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$installLog = Join-Path $logs 'install.log'
function Write-SetupLog([string]$Message) {
    $stamp = [DateTime]::UtcNow.ToString('yyyy-MM-dd HH:mm:ssZ')
    Add-Content -LiteralPath $installLog -Value "$stamp $Message" -Encoding UTF8
}
$stage = '读取安装参数'
Write-SetupLog '开始安装配置。'
try {
New-Item -ItemType Directory -Force $configRoot | Out-Null
if (!(Test-Path $configFile)) {
    $request = [Console]::In.ReadToEnd()
    # WSH/.NET redirected stdin may prepend a UTF-8 BOM. Python's json.load
    # rejects that marker, so remove it before forwarding the ASCII-safe JSON.
    if ($request.Length -gt 0 -and $request[0] -eq [char]0xFEFF) {
        $request = $request.Substring(1)
    }
    $c = $request | ConvertFrom-Json
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = Join-Path $InstallDir 'runtime\python.exe'
    $psi.Arguments = '-X utf8 "' + (Join-Path $InstallDir 'initialize.py') + '"'
    $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.RedirectStandardInput = $true
        $psi.RedirectStandardError = $true
        # The installer JSON serializer emits non-ASCII as \uXXXX. Keep this
        # ASCII stdin pipe compatible with Windows PowerShell 5.1/.NET Framework.
        $psi.StandardErrorEncoding = New-Object System.Text.UTF8Encoding($false)
    $stage = '初始化项目和管理员账号'
    $p = [System.Diagnostics.Process]::Start($psi)
    # Keep the pipe UTF-8. initialize.py accepts the optional BOM emitted by
    # some Windows PowerShell/.NET Framework redirected-input paths.
    $requestBytes = [System.Text.Encoding]::UTF8.GetBytes($request)
    $p.StandardInput.BaseStream.Write($requestBytes, 0, $requestBytes.Length)
    $p.StandardInput.BaseStream.Flush()
    $p.StandardInput.BaseStream.Close()
    $p.WaitForExit()
    if ($p.ExitCode) {
        $stderr = $p.StandardError.ReadToEnd()
        $detail = ($stderr -split '\r?\n' | Where-Object { $_ -match '^(?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception):' } | Select-Object -Last 1)
        if (!$detail) { $detail = '初始化程序未提供详细原因。' }
        $detail = $detail -replace '(?i)(password|密码)(\s*[:=]\s*)[^,\s;]+', '$1$2[已隐藏]'
        Write-SetupLog ("项目初始化失败（退出代码 {0}）：{1}" -f $p.ExitCode, $detail)
        throw '项目初始化失败，请查看 install.log。'
    }
    $c.PSObject.Properties.Remove('password')
    $stage = '保存不含密码的服务配置'
    $c | ConvertTo-Json | Set-Content $configFile -Encoding UTF8
}
$c = Get-Content $configFile -Raw | ConvertFrom-Json
$stage = '设置数据目录权限'
foreach ($directory in @($configRoot,$c.data_root,$c.backup_root)) {
    & icacls.exe $directory /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-19:(OI)(CI)M'
    if ($LASTEXITCODE) { throw 'Directory permissions failed' }
}
$escapedLogs = [System.Security.SecurityElement]::Escape($logs)
@"
<service>
 <id>BuildCostIQProjectServer</id>
 <name>BuildCostIQ Project Server</name>
 <description>Single construction project WebUI and API</description>
 <executable>%BASE%\runtime\python.exe</executable>
 <arguments>-X utf8 "%BASE%\launch.py"</arguments>
 <workingdirectory>%BASE%</workingdirectory>
 <startmode>Automatic</startmode>
 <serviceaccount><username>NT AUTHORITY\LocalService</username></serviceaccount>
 <onfailure action="restart" delay="10 sec"/>
 <stoptimeout>20 sec</stoptimeout>
 <logpath>$escapedLogs</logpath>
 <log mode="roll-by-size"><sizeThreshold>10240</sizeThreshold><keepFiles>5</keepFiles></log>
</service>
"@ | Set-Content (Join-Path $InstallDir 'BuildCostIQService.xml') -Encoding UTF8
if (!(Get-Service BuildCostIQProjectServer -ErrorAction SilentlyContinue)) {
    $stage = '注册 Windows 服务'
    & $service install
    if ($LASTEXITCODE) { throw 'Windows 服务注册失败。' }
}
$stage = '配置项目部局域网防火墙规则'
Get-NetFirewallRule -DisplayName 'BuildCostIQ Project Server' -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName 'BuildCostIQ Project Server' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8787 -Profile Private -RemoteAddress LocalSubnet | Out-Null
$stage = '启动 Windows 服务'
& $service start
if ($LASTEXITCODE) { throw 'Windows 服务启动失败。' }
$healthy = $false
$stage = '检查本机健康状态'
for ($i=0; $i -lt 30; $i++) {
    try {
        $h = Invoke-RestMethod 'http://127.0.0.1:8787/api/health' -TimeoutSec 2
        $running = (Get-Service BuildCostIQProjectServer -ErrorAction Stop).Status -eq 'Running'
        if ($running -and $h.service -eq 'BuildCostIQ WebUI' -and $h.runtime.version -eq '0.8.0-rc9') { $healthy=$true; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if (!$healthy) { throw '本机健康检查失败，请检查服务日志。' }
Write-SetupLog '服务启动且本机健康检查通过。'
} catch {
    $message = $_.Exception.Message -replace '(?i)(password|密码)(\s*[:=]\s*)[^,\s;]+', '$1$2[已隐藏]'
    try { Write-SetupLog ("安装配置失败（阶段：{0}）：{1}" -f $stage, $message) } catch {}
    throw
}
