param(
  [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$qilintexRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$repositoryRoot = (Resolve-Path (Join-Path $qilintexRoot "..")).Path
$stagingRoot = Join-Path $qilintexRoot ".desktop-staging"
$runtimeTarget = Join-Path $stagingRoot "runtime\python"
$agentTarget = Join-Path $stagingRoot "agent"

$resolvedStaging = [System.IO.Path]::GetFullPath($stagingRoot)
if (-not $resolvedStaging.StartsWith($qilintexRoot, [System.StringComparison]::OrdinalIgnoreCase) -or (Split-Path $resolvedStaging -Leaf) -ne ".desktop-staging") {
  throw "Refusing to clean unexpected staging path: $resolvedStaging"
}

if (-not $Python) {
  $Python = Join-Path $repositoryRoot ".runtime\python\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
  throw "Build Python not found: $Python"
}

$basePrefix = (& $Python -c "import sys; print(sys.base_prefix)").Trim()
$venvPrefix = (& $Python -c "import sys; print(sys.prefix)").Trim()
if (-not (Test-Path -LiteralPath (Join-Path $basePrefix "python.exe") -PathType Leaf)) {
  throw "Base Python runtime is not copyable: $basePrefix"
}
if (-not (Test-Path -LiteralPath (Join-Path $venvPrefix "Lib\site-packages") -PathType Container)) {
  throw "Virtual environment has no site-packages: $venvPrefix"
}

if (Test-Path -LiteralPath $stagingRoot) {
  $removed = $false
  foreach ($attempt in 1..5) {
    try {
      Remove-Item -LiteralPath $stagingRoot -Recurse -Force -ErrorAction Stop
      $removed = $true
      break
    } catch {
      if ($attempt -eq 5) { throw }
      Start-Sleep -Milliseconds (250 * $attempt)
    }
  }
  if (-not $removed -or (Test-Path -LiteralPath $stagingRoot)) {
    throw "Unable to clean desktop staging directory: $stagingRoot"
  }
}
New-Item -ItemType Directory -Path $runtimeTarget, $agentTarget -Force | Out-Null
if (-not (Test-Path -LiteralPath $runtimeTarget -PathType Container) -or -not (Test-Path -LiteralPath $agentTarget -PathType Container)) {
  throw "Desktop staging directories were not created correctly."
}

function Copy-Tree([string]$Source, [string]$Target, [string[]]$ExtraArgs = @()) {
  New-Item -ItemType Directory -Path $Target -Force | Out-Null
  $arguments = @($Source, $Target, "/E", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/XD", "__pycache__") + $ExtraArgs
  & robocopy @arguments | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "Directory copy failed: $Source -> $Target (robocopy $LASTEXITCODE)" }
}

foreach ($name in @("python.exe", "pythonw.exe", "python3.dll", "LICENSE", "LICENSE.txt")) {
  $source = Join-Path $basePrefix $name
  if (Test-Path -LiteralPath $source -PathType Leaf) { Copy-Item -LiteralPath $source -Destination $runtimeTarget -Force }
}
Get-ChildItem -LiteralPath $basePrefix -File -Filter "python*.dll" | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $runtimeTarget -Force }
Get-ChildItem -LiteralPath $basePrefix -File -Filter "vcruntime*.dll" | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $runtimeTarget -Force }

Copy-Tree (Join-Path $basePrefix "DLLs") (Join-Path $runtimeTarget "DLLs") @("/XF", "*.pyc")
Copy-Tree (Join-Path $basePrefix "Lib") (Join-Path $runtimeTarget "Lib") @("/XD", "site-packages", "/XF", "*.pyc")
Copy-Tree (Join-Path $venvPrefix "Lib\site-packages") (Join-Path $runtimeTarget "Lib\site-packages") @("/XF", "*.pyc")
Copy-Tree (Join-Path $venvPrefix "Scripts") (Join-Path $runtimeTarget "Scripts") @("/XF", "python.exe", "pythonw.exe", "*.pyc")

Get-ChildItem -LiteralPath $repositoryRoot -File -Filter "*.py" | ForEach-Object {
  Copy-Item -LiteralPath $_.FullName -Destination $agentTarget -Force
}
if (-not (Test-Path -LiteralPath (Join-Path $agentTarget "server.py") -PathType Leaf)) {
  throw "Local agent server.py is missing from desktop staging."
}
foreach ($directory in @("knowledge", "mcp_servers", "scripts", "skills")) {
  $source = Join-Path $repositoryRoot $directory
  if (Test-Path -LiteralPath $source -PathType Container) {
    Copy-Tree $source (Join-Path $agentTarget $directory) @("/XF", "*.pyc")
  }
}

$iconSource = Join-Path $qilintexRoot "apps\client\public\app-icon.jpg"
$iconTarget = Join-Path $qilintexRoot "apps\desktop\build\icon.ico"
New-Item -ItemType Directory -Path (Split-Path $iconTarget -Parent) -Force | Out-Null
$iconCode = "from PIL import Image; image=Image.open(r'$iconSource').convert('RGBA'); image.save(r'$iconTarget', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
& $Python -c $iconCode
if ($LASTEXITCODE -ne 0) { throw "Unable to generate the Windows app icon." }

& (Join-Path $runtimeTarget "python.exe") -c "import numpy, pandas, scipy, sklearn, matplotlib, openai_codex; print('portable runtime ok')"
if ($LASTEXITCODE -ne 0) { throw "Portable Python runtime self-check failed." }
& (Join-Path $runtimeTarget "python.exe") (Join-Path $agentTarget "server.py") --help | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Local agent package self-check failed." }

Write-Host "Desktop runtime prepared at $stagingRoot"
