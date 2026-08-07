param(
    [string]$MatlabRoot = "",
    [string]$Version = "latest"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$InstallDir = Join-Path $ProjectRoot ".agent-data\mcp"
$Binary = Join-Path $InstallDir "matlab-mcp-server-windows-x64.exe"

python -m pip install "mcp>=1.28.1,<2" "originpro>=1.1.15,<1.2"

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
$OriginInfo = python -m pip show originpro
$OriginPython = (($OriginInfo | Select-String "^Version:").Line -replace "^Version:\s*", "")

[pscustomobject]@{
    MatlabMcp = $ServerVersion
    Binary = $Binary
    Sha256 = (Get-FileHash -Algorithm SHA256 $Binary).Hash
    MatlabRoot = $MatlabRoot
    OriginPython = $OriginPython
} | Format-List
