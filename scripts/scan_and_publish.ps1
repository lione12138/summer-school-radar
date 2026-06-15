# Summer School Radar - daily local scan, commit, push, and deploy.
#
# Runs the scanner from this (residential) machine so Cloudflare datacenter-IP
# blocks do not apply, commits the data to main, and deploys the built site to
# the gh-pages branch (which GitHub Pages serves). Designed to be run by Windows
# Task Scheduler once a day; it is safe to run by hand too.
#
# It is resilient to outdoor / away conditions: it skips cleanly when there is
# no usable internet, logs everything, and never leaves the repo half-updated.

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
# exit code (unless -AllowFail, e.g. "git commit" with nothing to commit).
# Output is captured (not streamed) so git's normal stderr status lines do not
# surface as red PowerShell errors.
function Run([scriptblock]$block, [switch]$AllowFail) {
    $output = & $block 2>&1
    $code = $LASTEXITCODE
    if ($output) {
        Log (($output | ForEach-Object { "    " + $_.ToString() }) -join [Environment]::NewLine)
    }
    if (-not $AllowFail -and $code -ne 0) {
        throw "command failed (exit $code)"
    }
}

function Clean-SiteGit {
    $siteGit = Join-Path $repo "site\.git"
    if (Test-Path $siteGit) { Remove-Item -Recurse -Force $siteGit }
}

$repoUrl = "https://github.com/lione12138/summer-school-radar.git"
$env:PYTHONPATH = "src"

Log "=== run start ==="

# Connectivity precheck: skip cleanly when offline or on a captive/blocked
# network (cafe, hotspot with a login page, etc.). A later run recovers.
try {
    Invoke-WebRequest -Uri "https://github.com" -Method Head -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop | Out-Null
} catch {
    Log "No usable internet connection. Skipping this run."
    exit 0
}

try {
    Log "Syncing with remote (git pull --rebase)"
    Run { git pull --rebase --autostash }

    Log "Scanning from the local residential connection"
    Run { python -m research_school_radar.cli scan }

    Log "Committing data (reports, seen state, README)"
    Run { git add reports data/seen.json README.md }
    Run -AllowFail { git -c core.safecrlf=false commit -m "Daily local scan $(Get-Date -Format yyyy-MM-dd)" }

    Log "Pushing data to main"
    Run { git push }

    Log "Deploying site/ to the gh-pages branch"
    Clean-SiteGit
    $sitePath = Join-Path $repo "site"
    # site/ files may have been written by a different user/SID (e.g. a sandboxed
    # process); safe.directory=* lets git operate on them without complaint.
    $safe = "safe.directory=*"
    Push-Location $sitePath
    try {
        Run { git -c $safe init -q }
        Run { git -c $safe checkout -q -B gh-pages }
        Run { git -c $safe add -A }
        Run { git -c $safe -c user.email="local-scan@summer-school-radar" -c user.name="local-scan" -c core.safecrlf=false commit -q -m "Deploy $(Get-Date -Format yyyy-MM-dd)" }
        Run { git -c $safe push -q -f $repoUrl gh-pages }
    } finally {
        Pop-Location
        Clean-SiteGit
    }

    Log "=== run finished OK ==="
} catch {
    Log ("ERROR: " + $_.Exception.Message)
    Clean-SiteGit
    exit 1
}
