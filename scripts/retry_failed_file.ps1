param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath
)
$ErrorActionPreference = "Stop"
$dir = Split-Path $FilePath
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    Write-Output "Created directory: $dir"
}
# Remove any existing manifest so it won't be treated as fresh
$manifestPath = Join-Path $dir "manifest.json"
if (Test-Path $manifestPath) {
    Remove-Item $manifestPath -Force
    Write-Output "Removed existing manifest"
}
# Also remove exception file if exists
$exceptionPath = [System.IO.Path]::ChangeExtension($FilePath, ".md")
$exceptionDir = Split-Path $exceptionPath
if (Test-Path $exceptionDir) {
    # It's in conversion_exceptions, leave it
}
# Now run raw_derive.py directly
Write-Output "Running raw_derive.py for: $FilePath"
& (Join-Path $PSScriptRoot "raw_derive.py") $FilePath
