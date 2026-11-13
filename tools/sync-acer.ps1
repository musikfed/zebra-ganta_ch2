#Requires -Version 5.1
<#
Acer Swift 3: explicit sync from GitHub, run Python tests, optionally inspect
experiment 008 results stored on F:. Never opens or writes test HDD T:.
Use only from F:\zebra-ganta_ch2 and execute after each GitHub code update.
#>
[CmdletBinding()]
param(
    [switch]$Analyze008,
    [switch]$Plan008
)
$ErrorActionPreference = 'Stop'
$repo = 'F:\zebra-ganta_ch2'
if (-not (Test-Path -LiteralPath (Join-Path $repo '.git') -PathType Container)) {
    throw 'Repository missing at F:\zebra-ganta_ch2'
}
Set-Location -LiteralPath $repo
$branch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or $branch -ne 'main') {
    throw "Not on main ($branch). Sync refused."
}
$dirty = (& git status --porcelain)
if ($LASTEXITCODE -ne 0) { throw 'git status failed.' }
if ($dirty) {
    Write-Host 'Local files changed. Sync refused to prevent overwriting your work.' -ForegroundColor Yellow
    & git status --short
    throw 'Commit/stash carefully before updating; no automatic reset or clean.'
}
& git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Git update failed; do not run the new experiment.' }
Write-Host 'Updated commit:' -ForegroundColor Cyan
& git rev-parse --short HEAD
& uv run python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Python tests FAILED; physical experiment must not start.' }
if ($Plan008) {
    & uv run python experiment008.py
    if ($LASTEXITCODE -ne 0) { throw 'PLAN ONLY failed.' }
}
if ($Analyze008) {
    $path = 'results\20261113T120828Z-exp008-ntfs-hgst'
    if (-not (Test-Path (Join-Path $repo $path))) { throw "Expected existing run folder missing: $path" }
    & uv run python tools/report_exp008.py $path
    if ($LASTEXITCODE -ne 0) { throw 'Original data analysis failed.' }
}
Write-Host 'Acer sync and requested checks OK. No physical disk reads or writes were triggered.' -ForegroundColor Green
