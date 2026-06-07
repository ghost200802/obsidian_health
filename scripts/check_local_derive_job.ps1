param(
    [string]$JobId,
    [string]$JobDir,
    [switch]$ShowLogs
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$jobsRoot = Join-Path $repoRoot ".derived\job_runs"

if (-not $JobDir) {
    if (-not $JobId) {
        throw "Provide -JobId or -JobDir."
    }
    $JobDir = Join-Path $jobsRoot $JobId
}

if (-not (Test-Path -LiteralPath $JobDir)) {
    throw "Job directory not found: $JobDir"
}

$jobPath = Join-Path $JobDir "job.json"
$statusPath = Join-Path $JobDir "status.json"
$stdoutPath = Join-Path $JobDir "stdout.log"
$stderrPath = Join-Path $JobDir "stderr.log"

$job = Get-Content -LiteralPath $jobPath -Raw | ConvertFrom-Json
$status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json

$summary = [ordered]@{
    job_id = $job.job_id
    created_at = $job.created_at
    checked_at = $status.checked_at
    status = $status.status
    pid = $status.pid
    stdout_bytes = $status.stdout.bytes
    stderr_bytes = $status.stderr.bytes
    stdout_updated_at = $status.stdout.updated_at
    stderr_updated_at = $status.stderr.updated_at
}

if ($null -ne $status.exit_code) {
    $summary["exit_code"] = $status.exit_code
}

if ($ShowLogs) {
    $summary["stdout_tail"] = if (Test-Path -LiteralPath $stdoutPath) {
        Get-Content -LiteralPath $stdoutPath -Tail 20
    } else {
        @()
    }
    $summary["stderr_tail"] = if (Test-Path -LiteralPath $stderrPath) {
        Get-Content -LiteralPath $stderrPath -Tail 20
    } else {
        @()
    }
}

$summary | ConvertTo-Json -Depth 5
