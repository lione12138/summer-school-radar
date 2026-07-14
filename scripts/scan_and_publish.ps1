# Summa - local refresh/scan and snapshot publisher.
#
# Runs a no-network status refresh daily, and a DeepSeek-assisted full source
# scan on Monday, Wednesday, and Friday from this residential machine so Cloudflare
# datacenter-IP blocks do not apply. It commits a generated candidate snapshot
# to main; GitHub Actions is the only process allowed to publish gh-pages.
# Designed to be run by Windows Task Scheduler once a day; it is safe to run by
# hand too.
#
# It is resilient to outdoor / away conditions: it skips cleanly when there is
# no usable internet, logs everything, and never leaves the repo half-updated.

param(
    [ValidateSet("Auto", "Full", "Status")]
    [string]$Mode = "Auto"
)

# Native tools (git, python) write normal status to stderr; keep going and check
# exit codes explicitly so that does not look like a failure.
$ErrorActionPreference = "Continue"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("scan-" + (Get-Date -Format "yyyy-MM-dd") + ".log")
function Log([string]$msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg"
    # Appending can transiently fail if an indexer/antivirus has the log open;
    # retry a few times and, failing that, give up silently rather than letting
    # a log hiccup abort the whole publish.
    for ($i = 0; $i -lt 6; $i++) {
        try {
            Add-Content -LiteralPath $logFile -Value $line -ErrorAction Stop
            return
        } catch {
            Start-Sleep -Milliseconds 100
        }
    }
}

# Run a native command, log its output in one write, and throw on a non-zero
# exit code.
# Output is captured (not streamed) so git's normal stderr status lines do not
# surface as red PowerShell errors.
function Run([scriptblock]$block) {
    $output = & $block 2>&1
    $code = $LASTEXITCODE
    if ($output) {
        Log (($output | ForEach-Object { "    " + $_.ToString() }) -join [Environment]::NewLine)
    }
    if ($code -ne 0) {
        throw "command failed (exit $code)"
    }
}

function Run-WithRetry(
    [string]$operation,
    [scriptblock]$block,
    [int]$maxAttempts = 4
) {
    $delaySeconds = 5
    if ($env:SUMMA_GIT_RETRY_DELAY_SECONDS -match '^\d+$') {
        $delaySeconds = [int]$env:SUMMA_GIT_RETRY_DELAY_SECONDS
    }
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        try {
            Run $block
            return
        } catch {
            if ($attempt -ge $maxAttempts) {
                throw "$operation failed after $maxAttempts attempts"
            }
            Log "$operation failed (attempt $attempt/$maxAttempts); retrying in $delaySeconds seconds."
            if ($delaySeconds -gt 0) {
                Start-Sleep -Seconds $delaySeconds
            }
        }
    }
}

function Configure-GitNetworkProxy {
    # Git for Windows does not automatically inherit the per-user proxy used by
    # browsers. Prefer an explicit Git/environment setting, otherwise reuse a
    # reachable Windows Internet Settings proxy for this process only.
    $configuredProxy = & git config --get http.proxy 2>$null
    if ($LASTEXITCODE -eq 0 -and $configuredProxy) {
        Log "Git already has an explicit HTTP proxy configuration."
        return
    }
    if ($env:HTTPS_PROXY -or $env:HTTP_PROXY -or $env:ALL_PROXY) {
        Log "Git will use the proxy configured in the process environment."
        return
    }

    try {
        $internetSettings = Get-ItemProperty `
            "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" `
            -ErrorAction Stop
    } catch {
        return
    }
    if ([int]$internetSettings.ProxyEnable -ne 1 -or -not $internetSettings.ProxyServer) {
        return
    }

    $proxyValue = [string]$internetSettings.ProxyServer
    $proxyAddress = ""
    $entries = @($proxyValue -split ';' | Where-Object { $_ })
    foreach ($entry in $entries) {
        if ($entry -match '^https=(.+)$') {
            $proxyAddress = $matches[1]
            break
        }
    }
    if (-not $proxyAddress) {
        foreach ($entry in $entries) {
            if ($entry -match '^http=(.+)$') {
                $proxyAddress = $matches[1]
                break
            }
        }
    }
    if (-not $proxyAddress -and $entries.Count -eq 1) {
        $proxyAddress = $entries[0]
    }
    if (-not $proxyAddress) {
        return
    }
    if ($proxyAddress -notmatch '^[a-z][a-z0-9+.-]*://') {
        $proxyAddress = "http://$proxyAddress"
    }

    try {
        $proxyUri = [Uri]$proxyAddress
        if (-not $proxyUri.Host -or $proxyUri.Port -le 0) {
            return
        }
        $client = New-Object System.Net.Sockets.TcpClient
        try {
            $connected = $client.ConnectAsync($proxyUri.Host, $proxyUri.Port).Wait(1500)
            if (-not $connected -or -not $client.Connected) {
                return
            }
        } finally {
            $client.Dispose()
        }
    } catch {
        return
    }

    $configIndex = 0
    if ($env:GIT_CONFIG_COUNT -match '^\d+$') {
        $configIndex = [int]$env:GIT_CONFIG_COUNT
    }
    [Environment]::SetEnvironmentVariable(
        "GIT_CONFIG_KEY_$configIndex", "http.proxy", "Process"
    )
    [Environment]::SetEnvironmentVariable(
        "GIT_CONFIG_VALUE_$configIndex", $proxyAddress, "Process"
    )
    $env:GIT_CONFIG_COUNT = [string]($configIndex + 1)
    Log "Using the reachable Windows user proxy for Git network traffic."
}

function Require-NonEmptyFile([string]$path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "required generated artifact is missing: $path"
    }
    if ((Get-Item -LiteralPath $path).Length -le 0) {
        throw "required generated artifact is empty: $path"
    }
}

function Git-Revision([string]$revision) {
    $value = & git rev-parse $revision 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $value) {
        throw "could not resolve git revision: $revision"
    }
    return $value.ToString().Trim()
}

function Assert-OnlyExpectedChanges([string[]]$allowedPaths) {
    $allowed = @{}
    foreach ($path in $allowedPaths) {
        $allowed[$path.Replace("\", "/")] = $true
    }
    $statusLines = @(& git status --porcelain=v1 --untracked-files=normal)
    if ($LASTEXITCODE -ne 0) {
        throw "could not recheck git working tree"
    }
    $unexpected = @()
    foreach ($line in $statusLines) {
        if ($line.Length -lt 4) {
            continue
        }
        $path = $line.Substring(3).Trim().Replace("\", "/")
        if ($path.Contains(" -> ")) {
            $path = ($path -split " -> ", 2)[-1]
        }
        if (-not $allowed.ContainsKey($path)) {
            $unexpected += $path
        }
    }
    if ($unexpected.Count -gt 0) {
        throw "working tree changed during the run; refusing to commit: $($unexpected -join ', ')"
    }
}

function Restore-GeneratedWork([string[]]$paths) {
    # Only dedicated generated files are restored. Source files and README are
    # deliberately excluded so an edit made by the user during a long scan can
    # never be discarded by this scheduled task.
    $tracked = @()
    foreach ($path in $paths) {
        & git ls-files --error-unmatch -- $path 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $tracked += $path
        } else {
            $absolutePath = Join-Path $repo $path
            if (Test-Path -LiteralPath $absolutePath) {
                Remove-Item -LiteralPath $absolutePath -Force
            }
        }
    }
    if ($tracked.Count -gt 0) {
        & git restore --source=HEAD --staged --worktree -- $tracked 2>&1 | Out-Null
    }
}

$pendingPublishPath = Join-Path $repo ".git\summa-pending-publish.json"

function Save-PendingAutomationCommit(
    [string]$commit,
    [string]$baseCommit,
    [string]$message,
    [string[]]$paths
) {
    $payload = [ordered]@{
        schema_version = 1
        commit = $commit
        base_commit = $baseCommit
        message = $message
        paths = @($paths)
        queued_at = (Get-Date).ToUniversalTime().ToString("o")
    }
    $temporaryPath = "$pendingPublishPath.tmp"
    $payload | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temporaryPath -Encoding UTF8
    Move-Item -LiteralPath $temporaryPath -Destination $pendingPublishPath -Force
    Log "Saved generated commit $commit for a later publish retry."
}

function Clear-PendingAutomationCommit {
    if (Test-Path -LiteralPath $pendingPublishPath) {
        Remove-Item -LiteralPath $pendingPublishPath -Force
    }
}

function Test-AutomationGeneratedPath([string]$path) {
    $normalized = $path.Replace("\", "/")
    $fixedPaths = @(
        "data/latest_candidates.json",
        "data/latest_sources.json",
        "data/latest_scan_manifest.json",
        "data/review_queue.json",
        "data/seen.json"
    )
    return ($fixedPaths -contains $normalized) -or (
        $normalized -match '^reports/\d{4}-\d{2}-\d{2}\.md$'
    )
}

function Queue-PendingAutomationCommit(
    [string]$commit,
    [string]$baseCommit,
    [string]$message,
    [string[]]$paths
) {
    Save-PendingAutomationCommit $commit $baseCommit $message $paths
    & git update-ref refs/heads/main $baseCommit $commit 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "could not return main to its pre-automation commit after queueing generated output"
    }
    Restore-GeneratedWork $paths
    Log "Returned main to $baseCommit; generated output remains queued outside the working tree."
}

function Publish-PendingAutomationCommit {
    if (-not (Test-Path -LiteralPath $pendingPublishPath -PathType Leaf)) {
        return
    }

    try {
        $pending = Get-Content -LiteralPath $pendingPublishPath -Raw | ConvertFrom-Json
    } catch {
        throw "could not read pending automation commit metadata"
    }
    $pendingCommit = [string]$pending.commit
    $pendingBase = [string]$pending.base_commit
    $pendingMessage = [string]$pending.message
    $pendingPaths = @($pending.paths | ForEach-Object { [string]$_ })
    if (-not $pendingCommit -or -not $pendingBase -or $pendingPaths.Count -eq 0) {
        throw "pending automation commit metadata is incomplete"
    }
    $invalidPendingPaths = @($pendingPaths | Where-Object {
        -not (Test-AutomationGeneratedPath $_)
    })
    if ($invalidPendingPaths.Count -gt 0) {
        throw "pending automation metadata contains paths outside the generated-output allowlist"
    }

    & git cat-file -e "$pendingCommit`^{commit}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "pending automation commit no longer exists: $pendingCommit"
    }
    $actualParent = (& git rev-parse "$pendingCommit`^").ToString().Trim()
    if ($LASTEXITCODE -ne 0 -or $actualParent -ne $pendingBase) {
        throw "pending automation commit parent does not match its recorded base"
    }

    $allowed = @{}
    foreach ($path in $pendingPaths) {
        $allowed[$path.Replace("\", "/")] = $true
    }
    $unexpected = @(& git diff-tree --no-commit-id --name-only -r $pendingCommit | Where-Object {
        -not $allowed.ContainsKey($_.ToString().Replace("\", "/"))
    })
    if ($LASTEXITCODE -ne 0 -or $unexpected.Count -gt 0) {
        throw "pending automation commit contains unexpected paths"
    }

    $currentHead = Git-Revision "HEAD"
    $overlap = @(& git diff --name-only $pendingBase $currentHead -- $pendingPaths)
    if ($LASTEXITCODE -ne 0) {
        throw "could not compare pending generated paths with current main"
    }
    if ($overlap.Count -gt 0) {
        Log "Discarding stale pending output because newer main changed generated paths: $($overlap -join ', ')"
        Clear-PendingAutomationCommit
        return
    }

    Log "Recovering generated output queued after an earlier push failure."
    if ($currentHead -eq $pendingBase) {
        Run { git merge --ff-only $pendingCommit }
    } else {
        Run { git cherry-pick $pendingCommit }
    }
    $recoveredCommit = Git-Revision "HEAD"
    try {
        Run-WithRetry "git push for queued output" { git push }
    } catch {
        Save-PendingAutomationCommit $recoveredCommit $currentHead $pendingMessage $pendingPaths
        & git update-ref refs/heads/main $currentHead $recoveredCommit 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Restore-GeneratedWork $pendingPaths
        }
        throw
    }
    Clear-PendingAutomationCommit
    Log "Queued generated output was published successfully."
}

$env:PYTHONPATH = "src"

Log "=== run start ==="
Log "Requested mode: $Mode"
Configure-GitNetworkProxy
$generatedRunStarted = $false
$commitCreated = $false
$automationCommit = ""
$todayReport = "reports/$(Get-Date -Format yyyy-MM-dd).md"

try {
    # A scheduled job must never absorb or overwrite in-progress user edits.
    # Requiring a fully clean repository also lets the failure cleanup below
    # distinguish generated files from user-owned untracked files.
    $repoChanges = & git status --porcelain --untracked-files=normal
    if ($LASTEXITCODE -ne 0) {
        throw "could not inspect git working tree"
    }
    if ($repoChanges) {
        Log "Working tree has uncommitted or untracked changes. Skipping to protect user work."
        exit 0
    }

    $currentBranch = (& git branch --show-current).ToString().Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "could not inspect current git branch"
    }
    if ($currentBranch -ne "main") {
        Log "Current branch is '$currentBranch', not 'main'. Skipping to protect branch work."
        exit 0
    }

    $remoteAvailable = $true
    Log "Syncing with remote (git pull --ff-only, with retry)"
    try {
        Run-WithRetry "git pull --ff-only" { git pull --ff-only }
    } catch {
        $remoteAvailable = $false
        Log "GitHub is temporarily unavailable; continuing from the clean local main checkout."
    }

    if ($remoteAvailable) {
        $localRevision = Git-Revision "HEAD"
        if ($localRevision -ne (Git-Revision "origin/main")) {
            Log "Local main is not exactly synchronized with origin/main. Skipping instead of pushing unrelated commits."
            exit 0
        }
        Publish-PendingAutomationCommit
    } elseif (Test-Path -LiteralPath $pendingPublishPath -PathType Leaf) {
        Log "A generated commit is already waiting to be published; retaining it until GitHub is reachable."
        exit 1
    }
    $scanBaseCommit = Git-Revision "HEAD"

    $fullScanDays = @(
        [DayOfWeek]::Monday,
        [DayOfWeek]::Wednesday,
        [DayOfWeek]::Friday
    )
    $snapshotPath = Join-Path $repo "data\latest_candidates.json"
    $sourceSnapshot = Join-Path $repo "data\latest_sources.json"
    $manifestSnapshot = Join-Path $repo "data\latest_scan_manifest.json"
    $snapshotFiles = @($snapshotPath, $sourceSnapshot, $manifestSnapshot)
    $missingSnapshots = @($snapshotFiles | Where-Object {
        -not (Test-Path -LiteralPath $_ -PathType Leaf) -or (Get-Item -LiteralPath $_).Length -le 0
    })
    $hasCompleteSnapshot = $missingSnapshots.Count -eq 0
    $runFullScan = $false
    if ($Mode -eq "Full") {
        $runFullScan = $true
    } elseif ($Mode -eq "Status") {
        $runFullScan = $false
    } elseif ($fullScanDays -contains (Get-Date).DayOfWeek) {
        $runFullScan = $true
    } elseif (-not $hasCompleteSnapshot) {
        Log "The candidate/source/manifest snapshot is incomplete; falling back to a full scan."
        $runFullScan = $true
    }

    if (-not $runFullScan -and -not $hasCompleteSnapshot) {
        throw "status refresh requires non-empty candidate, source, and scan-manifest snapshots"
    }

    if ($runFullScan) {
        Log 'Checking semantic/LLM dependencies (install with: pip install -e ".[semantic,llm]")'
        Run { python -c "import sentence_transformers, dotenv; print('semantic/LLM dependencies OK')" }
        Log "Checking DeepSeek before the AI-assisted residential source scan"
        Run { python -m research_school_radar.ai_healthcheck --provider deepseek --strict }
        Log "Checking Brave Search (BRAVE_SEARCH_API_KEY) before refinement"
        Run { python -m research_school_radar.search_healthcheck --provider brave --strict }
        Log "Running AI-assisted full source scan from the local residential connection"
        $generatedRunStarted = $true
        Run { python -m research_school_radar.cli scan --enable-semantic --enable-llm-extraction --no-readme-update }
        Run { python -m research_school_radar.ai_output_validation --site-dir site }
    } else {
        Log "Running no-network status refresh from latest generated candidates"
        $siteSources = Join-Path $repo "site\sources.json"
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $siteSources) | Out-Null
        Copy-Item -LiteralPath $sourceSnapshot -Destination $siteSources -Force
        $generatedRunStarted = $true
        Run { python -m research_school_radar.cli refresh-status --candidates-json data/latest_candidates.json }
    }

    $generatedCandidates = Join-Path $repo "site\candidates.json"
    Require-NonEmptyFile $generatedCandidates
    $generatedSources = Join-Path $repo "site\sources.json"
    Require-NonEmptyFile $generatedSources
    Require-NonEmptyFile $manifestSnapshot

    if ($runFullScan) {
        Log "Validating candidate schema and retention before replacing the last known-good snapshot"
        Run {
            python -m research_school_radar.snapshot_validation `
                --candidate-json site/candidates.json `
                --previous-json data/latest_candidates.json
        }
        Copy-Item -LiteralPath $generatedCandidates -Destination $snapshotPath -Force
        Copy-Item -LiteralPath $generatedSources -Destination $sourceSnapshot -Force
    } else {
        Log "Status refresh does not replace source-scan snapshots."
    }

    $commitPaths = @("data/review_queue.json")
    if ($runFullScan) {
        $commitPaths += @(
            "data/latest_candidates.json",
            "data/latest_sources.json",
            "data/latest_scan_manifest.json",
            "data/seen.json"
        )
        if (Test-Path (Join-Path $repo $todayReport)) {
            $commitPaths += $todayReport
        }
        $commitMessage = "Full local scan $(Get-Date -Format yyyy-MM-dd)"
    } else {
        $commitMessage = "Daily status refresh $(Get-Date -Format yyyy-MM-dd)"
    }

    Assert-OnlyExpectedChanges $commitPaths

    if ((Git-Revision "HEAD") -ne $scanBaseCommit) {
        throw "local HEAD changed while the scan was running"
    }
    if ($remoteAvailable) {
        Log "Checking that origin/main did not advance during the scan"
        try {
            Run-WithRetry "git fetch origin main" { git fetch origin main }
        } catch {
            $remoteAvailable = $false
            Log "GitHub became unavailable after generation; output will be queued locally."
        }
    }
    if ($remoteAvailable -and (Git-Revision "origin/main") -ne $scanBaseCommit) {
        throw "origin/main advanced while the scan was running; retaining the previous successful snapshot"
    }

    Log "Staging generated data only: $($commitPaths -join ', ')"
    Run { git add -- $commitPaths }
    Run { git diff --cached --check }
    & git diff --cached --quiet
    $stagedDiff = $LASTEXITCODE
    if ($stagedDiff -eq 1) {
        # A real commit failure is fatal. Only the explicit quiet-diff check is
        # allowed to classify an unchanged run as success.
        Run { git -c core.safecrlf=false commit -m $commitMessage }
        $commitCreated = $true
        $automationCommit = Git-Revision "HEAD"
    } elseif ($stagedDiff -eq 0) {
        Log "Generated data is unchanged; no commit needed."
    } else {
        throw "could not inspect staged changes"
    }

    if ($commitCreated -and -not $remoteAvailable) {
        Queue-PendingAutomationCommit $automationCommit $scanBaseCommit $commitMessage $commitPaths
        $commitCreated = $false
        throw "generated output is queued because GitHub is unavailable"
    }

    if ($remoteAvailable) {
        Log "Pushing data to main"
        try {
            Run-WithRetry "git push" { git push }
        } catch {
            if ($commitCreated -and $automationCommit) {
                Queue-PendingAutomationCommit $automationCommit $scanBaseCommit $commitMessage $commitPaths
                $commitCreated = $false
            }
            throw
        }
    } else {
        Log "Generated data is unchanged, so there is no pending commit to publish."
    }

    if ($remoteAvailable) {
        Log "Snapshot synchronized. GitHub Actions will build and publish gh-pages."
    } else {
        Log "Local generation completed with no changed data to publish."
    }
    Log "=== run finished OK ==="
} catch {
    Log ("ERROR: " + $_.Exception.Message)
    if ($generatedRunStarted -and -not $commitCreated) {
        Log "Restoring generated tracked files after the failed run."
        Restore-GeneratedWork @(
            "data/latest_candidates.json",
            "data/latest_sources.json",
            "data/latest_scan_manifest.json",
            "data/review_queue.json",
            "data/seen.json",
            $todayReport
        )
    }
    exit 1
}
