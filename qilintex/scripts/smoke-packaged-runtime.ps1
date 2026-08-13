param([int]$Port = 8876)

$ErrorActionPreference = "Stop"
$qilintexRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repositoryRoot = (Resolve-Path (Join-Path $qilintexRoot "..")).Path
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
  throw "Port $Port is already in use."
}

$smokeRoot = Join-Path $repositoryRoot ".codex-temp\app-smoke-final"
New-Item -ItemType Directory -Path $smokeRoot -Force | Out-Null
$env:AGENT_DATA_DIR = $smokeRoot
$env:CODEX_LOGIN_FLOW = "browser"
$python = (Resolve-Path (Join-Path $qilintexRoot "release\win-unpacked\resources\runtime\python\python.exe")).Path
$server = (Resolve-Path (Join-Path $qilintexRoot "release\win-unpacked\resources\agent\server.py")).Path
$stdout = Join-Path $smokeRoot "stdout.log"
$stderr = Join-Path $smokeRoot "stderr.log"
$process = Start-Process -FilePath $python -ArgumentList @($server, "--host", "127.0.0.1", "--port", [string]$Port, "--frontend-url", "https://qilintex.top/") -WorkingDirectory (Split-Path $server -Parent) -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
try {
  $ready = $false
  for ($index = 0; $index -lt 40; $index += 1) {
    Start-Sleep -Milliseconds 500
    try {
      $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 2
      $ready = $true
      break
    } catch {}
  }
  if (-not $ready) {
    throw "Packaged agent did not become ready. STDERR: $(Get-Content $stderr -Raw -ErrorAction SilentlyContinue)"
  }
  $config = Invoke-RestMethod "http://127.0.0.1:$Port/api/config" -TimeoutSec 20
  [pscustomobject]@{
    Health = $health.ok
    Service = $health.service
    Version = $health.version
    CredentialStorage = $config.credentialStorage
    ActiveProvider = $config.activeProvider
    RuntimePython = $python
    AgentServer = $server
  } | Format-List
} finally {
  if (-not $process.HasExited) { Stop-Process -Id $process.Id -Force }
  Remove-Item Env:AGENT_DATA_DIR -ErrorAction SilentlyContinue
  Remove-Item Env:CODEX_LOGIN_FLOW -ErrorAction SilentlyContinue
}
