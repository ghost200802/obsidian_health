param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Paths,

    [switch]$Force,

    [ValidateRange(1, 1000)]
    [int]$ProgressEveryPages = 10
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
$manifestPath = Join-Path $jobDir "job.json"
$pathsPath = Join-Path $jobDir "paths.txt"
$argsPath = Join-Path $jobDir "args.txt"
$progressPath = Join-Path $jobDir "progress.json"
$exitCodePath = Join-Path $jobDir "exit_code.txt"
$launcherScriptPath = Join-Path $jobDir "launcher.ps1"

$resolvedPaths = foreach ($path in $Paths) {
    $resolved = Resolve-Path -LiteralPath $path
    $resolved.Path
}

Set-Content -LiteralPath $pathsPath -Value $resolvedPaths -Encoding UTF8

$argumentList = @(
    $deriveScript,
    "--json",
    "--progress-path", $progressPath,
    "--progress-every-pages", $ProgressEveryPages
)
if ($Force) {
    $argumentList += "--force"
}
$argumentList += $resolvedPaths

Set-Content -LiteralPath $argsPath -Value $argumentList -Encoding UTF8

$jobPayload = [ordered]@{
    job_id = $jobId
    created_at = (Get-Date).ToString("o")
    repo_root = $repoRoot
    progress_every_pages = $ProgressEveryPages
    command = [ordered]@{
        python = $pythonExe
        script = $deriveScript
        arguments = $argumentList
    }
    paths_file = $pathsPath
    args_file = $argsPath
    progress_file = $progressPath
    stdout_log = $stdoutPath
    stderr_log = $stderrPath
    exit_code_file = $exitCodePath
}
$jobPayload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$initialProgress = [ordered]@{
    updated_at = (Get-Date).ToString("o")
    status = "queued"
    phase = "job_created"
    files_total = $resolvedPaths.Count
    files_completed = 0
    failed_files = 0
    current_file_index = $null
    current_source = $null
    total_pages = $null
    processed_pages = $null
    current_page = $null
}
$initialProgress | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $progressPath -Encoding UTF8

$launcherScript = @"
param(
    [string]`$PythonExe,
    [string]`$ExitCodePath,
    [string]`$ArgsFilePath
)

`$ScriptArgs = Get-Content -LiteralPath `$ArgsFilePath -Encoding UTF8
& `$PythonExe @ScriptArgs
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
    "-ArgsFilePath", $argsPath
)

$deriveProcess = Start-Process -FilePath "powershell.exe" `
    -ArgumentList $launcherArgs `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru `
    -WindowStyle Hidden

$jobPayload["pid"] = $deriveProcess.Id
$jobPayload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

[ordered]@{
    job_id = $jobId
    pid = $deriveProcess.Id
    status = "running"
    job_dir = $jobDir
    progress_file = $progressPath
    stdout_log = $stdoutPath
    stderr_log = $stderrPath
    check_command = ".\scripts\check_local_derive_job.ps1 -JobId $jobId"
} | ConvertTo-Json -Depth 5
