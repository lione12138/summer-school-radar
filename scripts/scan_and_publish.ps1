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

$env:PYTHONPATH = "src"

Log "=== run start ==="
Log "Requested mode: $Mode"
$generatedRunStarted = $false
$commitCreated = $false
$automationCommit = ""
$todayReport = "reports/$(Get-Date -Format yyyy-MM-dd).md"

# Connectivity precheck: skip cleanly when offline or on a captive/blocked
# network (cafe, hotspot with a login page, etc.). A later run recovers.
try {
    Invoke-WebRequest -Uri "https://github.com" -Method Head -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop | Out-Null
} catch {
    Log "No usable internet connection. Skipping this run."
    exit 0
}

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

    Log "Syncing with remote (git pull --ff-only)"
    Run { git pull --ff-only }
    $scanBaseCommit = Git-Revision "HEAD"
    if ($scanBaseCommit -ne (Git-Revision "origin/main")) {
        Log "Local main is not exactly synchronized with origin/main. Skipping instead of pushing unrelated commits."
        exit 0
    }

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
    Log "Checking that origin/main did not advance during the scan"
    Run { git fetch origin main }
    if ((Git-Revision "origin/main") -ne $scanBaseCommit) {
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

    Log "Pushing data to main"
    try {
        Run { git push }
    } catch {
        if ($commitCreated -and $automationCommit) {
            # Roll back only the exact commit this invocation created. The
            # expected-old-value argument makes this a no-op if HEAD changed
            # (for example, because the user committed while the push ran).
            & git update-ref refs/heads/main $scanBaseCommit $automationCommit 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $commitCreated = $false
                Log "Push failed; removed the unpushed automation commit so the next scheduled run can recover."
            } else {
                Log "Push failed and HEAD changed; left the branch untouched for manual inspection."
            }
        }
        throw
    }

    Log "Snapshot pushed. GitHub Actions will build and publish gh-pages."
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
