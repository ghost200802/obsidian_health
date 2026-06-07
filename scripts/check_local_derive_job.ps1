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
$progressPath = Join-Path $JobDir "progress.json"
$stdoutPath = Join-Path $JobDir "stdout.log"
$stderrPath = Join-Path $JobDir "stderr.log"
$exitCodePath = Join-Path $JobDir "exit_code.txt"

$job = Get-Content -LiteralPath $jobPath -Raw -Encoding UTF8 | ConvertFrom-Json
$progress = if (Test-Path -LiteralPath $progressPath) {
    Get-Content -LiteralPath $progressPath -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
    $null
}

$processId = $null
try {
    $processId = [int]$job.pid
} catch {
}

$isRunning = $false
if ($processId) {
    $isRunning = $null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)
}

function Get-LogInfo {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        $item = Get-Item -LiteralPath $Path
        return @{
            bytes = $item.Length
            updated_at = $item.LastWriteTime.ToString("o")
        }
    }
    return @{
        bytes = 0
        updated_at = $null
    }
}

$summary = [ordered]@{
    job_id = $job.job_id
    created_at = $job.created_at
    checked_at = (Get-Date).ToString("o")
    status = if ($isRunning) { "running" } elseif (Test-Path -LiteralPath $exitCodePath) { "finished" } else { "unknown" }
    pid = $processId
    progress_updated_at = if ($progress) { $progress.updated_at } else { $null }
    phase = if ($progress) { $progress.phase } else { $null }
    files_total = if ($progress) { $progress.files_total } else { $null }
    files_completed = if ($progress) { $progress.files_completed } else { $null }
    failed_files = if ($progress) { $progress.failed_files } else { $null }
    skipped_files = if ($progress) { $progress.skipped_files } else { $null }
    current_file_index = if ($progress) { $progress.current_file_index } else { $null }
    current_source = if ($progress) { $progress.current_source } else { $null }
    current_kind = if ($progress) { $progress.current_kind } else { $null }
    total_pages = if ($progress) { $progress.total_pages } else { $null }
    processed_pages = if ($progress) { $progress.processed_pages } else { $null }
    current_page = if ($progress) { $progress.current_page } else { $null }
    method = if ($progress) { $progress.method } else { $null }
    stdout = Get-LogInfo -Path $stdoutPath
    stderr = Get-LogInfo -Path $stderrPath
}

if (Test-Path -LiteralPath $exitCodePath) {
    $summary["exit_code"] = (Get-Content -LiteralPath $exitCodePath -Raw -Encoding ASCII).Trim()
}

if ($ShowLogs) {
    $summary["stdout_tail"] = if (Test-Path -LiteralPath $stdoutPath) {
        Get-Content -LiteralPath $stdoutPath -Tail 20 -Encoding UTF8
    } else {
        @()
    }
    $summary["stderr_tail"] = if (Test-Path -LiteralPath $stderrPath) {
        Get-Content -LiteralPath $stderrPath -Tail 20 -Encoding UTF8
    } else {
        @()
    }
}

$summary | ConvertTo-Json -Depth 5
