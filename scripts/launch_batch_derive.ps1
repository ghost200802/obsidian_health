param(
    [Parameter(Mandatory = $true)]
    [string]$RawDir
)

$ErrorActionPreference = "Stop"

$pdfFiles = Get-ChildItem -LiteralPath $RawDir -Filter "*.pdf" -Recurse |
    Where-Object { $_.Name -notlike "._*" } |
    Select-Object -ExpandProperty FullName

if ($pdfFiles.Count -eq 0) {
    Write-Output "No PDF files found in: $RawDir"
    exit 0
}

Write-Output "Found $($pdfFiles.Count) PDF files"
& (Join-Path $PSScriptRoot "start_local_derive_job.ps1") @pdfFiles
