# Run production scans independently of the developer's working tree.
param(
    [ValidateSet("Auto", "Full", "Status")][string]$Mode = "Auto",
    [string]$RuntimePath = "",
    [switch]$PrepareOnly
)
$ErrorActionPreference = "Stop"
$developmentRepo = Split-Path -Parent $PSScriptRoot
if (-not $RuntimePath) {
    $hash = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash(
        [Text.Encoding]::UTF8.GetBytes($developmentRepo.ToLowerInvariant()))).Replace("-", "").Substring(0, 12)
    # USERPROFILE avoids MSIX LocalAppData virtualization: the desktop app
    # and Task Scheduler must operate on the very same checkout and lock.
    $RuntimePath = Join-Path $env:USERPROFILE ".summa\scan-$hash"
}
$RuntimePath = [IO.Path]::GetFullPath($RuntimePath)
if ($RuntimePath -eq $developmentRepo -or $RuntimePath.StartsWith($developmentRepo + "\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "The scan runtime must be outside the development checkout."
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $RuntimePath) | Out-Null
$lock = $null
try {
    $lock = [IO.File]::Open("$RuntimePath.lock", 'OpenOrCreate', 'ReadWrite', 'None')
    $remote = & git -C $developmentRepo remote get-url origin
    if ($LASTEXITCODE -ne 0) { throw "Cannot read the production remote." }
    if (-not (Test-Path -LiteralPath $RuntimePath)) {
        & git clone --no-hardlinks --branch main $developmentRepo $RuntimePath
        if ($LASTEXITCODE -ne 0) { throw "Cannot create isolated scan checkout." }
        & git -C $RuntimePath remote set-url origin $remote
        if ($LASTEXITCODE -ne 0) { throw "Cannot configure production remote." }
    }
    $runtimeRemote = & git -C $RuntimePath remote get-url origin
    if ($LASTEXITCODE -ne 0 -or $runtimeRemote -ne $remote) { throw "Unexpected runtime repository." }
    foreach ($identityKey in @('user.name', 'user.email')) {
        $identityValue = & git -C $developmentRepo config --get $identityKey
        if ($LASTEXITCODE -ne 0 -or -not $identityValue) { throw "Missing Git $identityKey in development repository." }
        & git -C $RuntimePath config --local $identityKey $identityValue
        if ($LASTEXITCODE -ne 0) { throw "Cannot configure runtime Git $identityKey." }
    }
    # Keys remain local ignored files; never emit their contents or commit them.
    foreach ($name in @('.env', '.env.local')) {
        $inputFile = Join-Path $developmentRepo $name
        if (Test-Path -LiteralPath $inputFile) {
            Copy-Item -LiteralPath $inputFile -Destination (Join-Path $RuntimePath $name) -Force
        }
    }
    $venvBin = Join-Path $developmentRepo '.venv\Scripts'
    if (Test-Path -LiteralPath (Join-Path $venvBin 'python.exe')) { $env:PATH = "$venvBin;$env:PATH" }
    # Editable installs can point at the developer checkout: force runtime code.
    $env:PYTHONPATH = Join-Path $RuntimePath 'src'
    Write-Output "Summa scan runtime: $RuntimePath"
    if (-not $PrepareOnly) {
        & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File (Join-Path $RuntimePath 'scripts\scan_and_publish.ps1') -Mode $Mode
        if ($LASTEXITCODE -ne 0) { throw "Isolated scan failed (exit $LASTEXITCODE); inspect runtime logs." }
    }
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
} finally {
    if ($lock) { $lock.Dispose() }
}
