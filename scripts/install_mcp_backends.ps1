param(
    [string]$MatlabRoot = "",
    [string]$Version = "latest"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DataRoot = if ($env:AGENT_DATA_DIR) {
    if ([System.IO.Path]::IsPathRooted($env:AGENT_DATA_DIR)) { $env:AGENT_DATA_DIR } else { Join-Path $ProjectRoot $env:AGENT_DATA_DIR }
} else {
    Join-Path $ProjectRoot ".agent-data"
}
$InstallDir = Join-Path $DataRoot "mcp"
$Binary = Join-Path $InstallDir "matlab-mcp-server-windows-x64.exe"
$ManagedPython = Join-Path $ProjectRoot ".runtime\python\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $ManagedPython) { $ManagedPython } else { (Get-Command python -ErrorAction Stop).Source }

& $Python -m pip install "mcp>=1.28.1,<2" "originpro>=1.1.15,<1.2"

$ReleaseUri = if ($Version -eq "latest") {
    "https://api.github.com/repos/matlab/matlab-mcp-server/releases/latest"
} else {
    "https://api.github.com/repos/matlab/matlab-mcp-server/releases/tags/$Version"
}
$Release = Invoke-RestMethod -Headers @{ "User-Agent" = "Math-Modeling-Agent" } -Uri $ReleaseUri
$Asset = $Release.assets | Where-Object { $_.name -eq "matlab-mcp-server-windows-x64.exe" } | Select-Object -First 1
if (-not $Asset) {
    throw "The MathWorks release does not contain a Windows x64 MCP Server."
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $Binary
$ServerVersion = & $Binary --version

if (-not $MatlabRoot) {
    $Matlab = Get-Command matlab -ErrorAction SilentlyContinue
    if ($Matlab) {
        $MatlabRoot = Split-Path -Parent (Split-Path -Parent $Matlab.Source)
    }
}
$OriginInfo = & $Python -m pip show originpro
$OriginPython = (($OriginInfo | Select-String "^Version:").Line -replace "^Version:\s*", "")

[pscustomobject]@{
    MatlabMcp = $ServerVersion
    Binary = $Binary
    Sha256 = (Get-FileHash -Algorithm SHA256 $Binary).Hash
    MatlabRoot = $MatlabRoot
    OriginPython = $OriginPython
} | Format-List
