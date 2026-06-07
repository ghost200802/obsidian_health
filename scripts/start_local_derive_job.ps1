param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Paths,

    [switch]$Force,

    [ValidateRange(1, 1440)]
    [int]$SnapshotMinutes = 1
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot ".venv-mineru\Scripts\python.exe"
$deriveScript = Join-Path $repoRoot "scripts\raw_derive.py"
$jobsRoot = Join-Path $repoRoot ".derived\job_runs"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Missing Python runtime: $pythonExe"
}

if (-not (Test-Path -LiteralPath $deriveScript)) {
    throw "Missing derive script: $deriveScript"
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$jobId = "derive-$timestamp"
$jobDir = Join-Path $jobsRoot $jobId
$null = New-Item -ItemType Directory -Path $jobDir -Force

$stdoutPath = Join-Path $jobDir "stdout.log"
$stderrPath = Join-Path $jobDir "stderr.log"
$statusPath = Join-Path $jobDir "status.json"
$manifestPath = Join-Path $jobDir "job.json"
$pathsPath = Join-Path $jobDir "paths.txt"
$exitCodePath = Join-Path $jobDir "exit_code.txt"
$launcherScriptPath = Join-Path $jobDir "launcher.ps1"
$watcherScriptPath = Join-Path $jobDir "watcher.ps1"

$resolvedPaths = foreach ($path in $Paths) {
    $resolved = Resolve-Path -LiteralPath $path
    $resolved.Path
}

Set-Content -LiteralPath $pathsPath -Value $resolvedPaths -Encoding UTF8

$argumentList = @(
    $deriveScript,
    "--json"
)
if ($Force) {
    $argumentList += "--force"
}
$argumentList += $resolvedPaths

$jobPayload = [ordered]@{
    job_id = $jobId
    created_at = (Get-Date).ToString("o")
    repo_root = $repoRoot
    command = [ordered]@{
        python = $pythonExe
        script = $deriveScript
        arguments = $argumentList
    }
    paths_file = $pathsPath
    stdout_log = $stdoutPath
    stderr_log = $stderrPath
    status_file = $statusPath
    exit_code_file = $exitCodePath
    snapshot_minutes = $SnapshotMinutes
}
$jobPayload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$launcherScript = @"
param(
    [string]`$PythonExe,
    [string]`$ExitCodePath,
    [string[]]`$Args
)

& `$PythonExe @Args
`$LASTEXITCODE | Set-Content -LiteralPath `$ExitCodePath -Encoding ASCII
exit `$LASTEXITCODE
"@

Set-Content -LiteralPath $launcherScriptPath -Value $launcherScript -Encoding UTF8

$launcherArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $launcherScriptPath,
    "-PythonExe", $pythonExe,
    "-ExitCodePath", $exitCodePath,
    "-Args"
)
$launcherArgs += $argumentList

$deriveProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $launcherArgs `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru `
    -WindowStyle Hidden

$watcherScript = @"
param(
    [int]`$TargetPid,
    [string]`$StatusPath,
    [string]`$StdoutPath,
    [string]`$StderrPath,
    [string]`$ExitCodePath,
    [int]`$SnapshotMinutes
)

`$ErrorActionPreference = "Stop"

function Get-LogInfo {
    param([string]`$Path)
    if (Test-Path -LiteralPath `$Path) {
        `$item = Get-Item -LiteralPath `$Path
        return @{
            exists = `$true
            bytes = `$item.Length
            updated_at = `$item.LastWriteTime.ToString("o")
        }
    }
    return @{
        exists = `$false
        bytes = 0
        updated_at = `$null
    }
}

while (`$true) {
    `$process = Get-Process -Id `$TargetPid -ErrorAction SilentlyContinue
    if (`$null -eq `$process) {
        break
    }

    `$payload = [ordered]@{
        checked_at = (Get-Date).ToString("o")
        status = "running"
        pid = `$TargetPid
        stdout = Get-LogInfo -Path `$StdoutPath
        stderr = Get-LogInfo -Path `$StderrPath
    }
    `$payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath `$StatusPath -Encoding UTF8
    Start-Sleep -Seconds ([Math]::Max(60, `$SnapshotMinutes * 60))
}

`$exitCode = if (Test-Path -LiteralPath `$ExitCodePath) {
    Get-Content -LiteralPath `$ExitCodePath -Raw
} else {
    `$null
}

`$finalPayload = [ordered]@{
    checked_at = (Get-Date).ToString("o")
    status = "finished"
    pid = `$TargetPid
    exit_code = `$exitCode
    stdout = Get-LogInfo -Path `$StdoutPath
    stderr = Get-LogInfo -Path `$StderrPath
}
`$finalPayload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath `$StatusPath -Encoding UTF8
"@

Set-Content -LiteralPath $watcherScriptPath -Value $watcherScript -Encoding UTF8

$watcherArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $watcherScriptPath,
    "-TargetPid", $deriveProcess.Id,
    "-StatusPath", $statusPath,
    "-StdoutPath", $stdoutPath,
    "-StderrPath", $stderrPath,
    "-ExitCodePath", $exitCodePath,
    "-SnapshotMinutes", $SnapshotMinutes
)

Start-Process -FilePath "powershell.exe" `
    -ArgumentList $watcherArgs `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden | Out-Null

$initialStatus = [ordered]@{
    checked_at = (Get-Date).ToString("o")
    status = "running"
    pid = $deriveProcess.Id
    stdout = @{
        exists = $false
        bytes = 0
        updated_at = $null
    }
    stderr = @{
        exists = $false
        bytes = 0
        updated_at = $null
    }
}
$initialStatus | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statusPath -Encoding UTF8

[ordered]@{
    job_id = $jobId
    pid = $deriveProcess.Id
    status = "running"
    job_dir = $jobDir
    status_file = $statusPath
    stdout_log = $stdoutPath
    stderr_log = $stderrPath
    check_command = ".\scripts\check_local_derive_job.ps1 -JobId $jobId"
} | ConvertTo-Json -Depth 5
