# Summer School Radar - daily local scan, commit, push, and deploy.
#
# Runs the scanner from this (residential) machine so Cloudflare datacenter-IP
# blocks do not apply, commits the data to main, and deploys the built site to
# the gh-pages branch (which GitHub Pages serves). Designed to be run by Windows
# Task Scheduler once a day; it is safe to run by hand too.
#
# It is resilient to outdoor / away conditions: it skips cleanly when there is
# no usable internet, logs everything, and never leaves the repo in a half
# state.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$logDir = Join-Path $repo "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("scan-" + (Get-Date -Format "yyyy-MM-dd") + ".log")
function Log([string]$msg) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" | Tee-Object -FilePath $logFile -Append | Out-Null
}

$repoUrl = "https://github.com/lione12138/summer-school-radar.git"
$env:PYTHONPATH = "src"

Log "=== run start ==="

# Connectivity precheck: skip cleanly when offline or on a captive/blocked
# network (cafe, hotspot with a login page, etc.). A later run recovers.
try {
    Invoke-WebRequest -Uri "https://github.com" -Method Head -TimeoutSec 15 -UseBasicParsing | Out-Null
} catch {
    Log "No usable internet connection. Skipping this run."
    exit 0
}

function Clean-SiteGit {
    $siteGit = Join-Path $repo "site\.git"
    if (Test-Path $siteGit) { Remove-Item -Recurse -Force $siteGit }
}

try {
    Log "Syncing with remote (git pull --rebase)"
    git pull --rebase --autostash 2>&1 | Tee-Object -FilePath $logFile -Append

    Log "Scanning from the local residential connection"
    python -m research_school_radar.cli scan 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) { throw "scan failed (exit code $LASTEXITCODE)" }

    Log "Committing data (reports, seen state, README)"
    git add reports data/seen.json README.md
    git -c core.safecrlf=false commit -m "Daily local scan $(Get-Date -Format yyyy-MM-dd)" 2>&1 |
        Tee-Object -FilePath $logFile -Append
    # An empty commit (no changes) is fine; git just reports nothing to commit.

    Log "Pushing data to main"
    git push 2>&1 | Tee-Object -FilePath $logFile -Append

    Log "Deploying site/ to the gh-pages branch"
    Clean-SiteGit
    Push-Location (Join-Path $repo "site")
    try {
        git init -q
        git checkout -q -B gh-pages
        git add -A
        git -c user.email="local-scan@summer-school-radar" -c user.name="local-scan" `
            -c core.safecrlf=false commit -q -m "Deploy $(Get-Date -Format yyyy-MM-dd)"
        git push -q -f $repoUrl gh-pages 2>&1 | Tee-Object -FilePath $logFile -Append
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
