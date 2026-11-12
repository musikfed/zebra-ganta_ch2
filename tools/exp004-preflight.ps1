# Experiment 004 hardware preflight. No write access, no disk reads, no changes.
# Run after USBView confirms the ORICO VIA Labs 2109:0715 SuperSpeed port.
$ErrorActionPreference = 'Stop'
Write-Host '=== Zebra Ganta / Experiment 004 / ORICO preflight ===' -ForegroundColor Cyan
$all = @(Get-Disk)
$wmi = @(Get-CimInstance Win32_DiskDrive)
$candidates = @()
foreach ($d in $all) {
    $w = @($wmi | Where-Object { $_.Index -eq $d.Number } | Select-Object -First 1)
    $p = @(Get-Partition -DiskNumber $d.Number -ErrorAction SilentlyContinue)
    $letters = @( $p | Where-Object { $_.DriveLetter } | ForEach-Object { $_.DriveLetter.ToString() } )
    $name = ([string]$d.FriendlyName) + ' ' + ([string]$w.Model)
    $matchesModel = (($name -replace '[^A-Za-z0-9]','').ToUpperInvariant().Contains('HTS725050B7E630'))
    $expectedCapacity = ([int64]$d.Size -eq 500106780160)
    $candidate = [pscustomobject]@{
        Number=$d.Number
        FriendlyName=$d.FriendlyName
        Model=[string]$w.Model
        BusType=[string]$d.BusType
        GetDiskSize=[int64]$d.Size
        Win32Size=[int64]$w.Size
        Letters=($letters -join ',')
        IsBoot=[bool]$d.IsBoot
        IsSystem=[bool]$d.IsSystem
        IsOffline=[bool]$d.IsOffline
        OperationalStatus=[string]$d.OperationalStatus
        PNPDeviceID=[string]$w.PNPDeviceID
        HGSTModelMatch=[bool]$matchesModel
        GetDiskSizeMatch=[bool]$expectedCapacity
    }
    $candidates += $candidate
}
$candidates | Format-Table Number,FriendlyName,Model,BusType,GetDiskSize,Win32Size,Letters,HGSTModelMatch -AutoSize
Write-Host ''
$matched = @($candidates | Where-Object { $_.HGSTModelMatch -and $_.GetDiskSizeMatch -and $_.BusType -eq 'USB' -and !$_.IsSystem -and !$_.IsBoot -and !$_.IsOffline })
if ($matched.Count -ne 1) {
    Write-Host '[WARN] Expected exactly one non-system HGST USB disk with documented Get-Disk size; found:' $matched.Count -ForegroundColor Yellow
    Write-Host '[WARN] Do not start experiment004.py. Inspect the inventory and USB bridge identity.'
} else {
    $target=$matched[0]
    Write-Host '[OK] Candidate verified by Windows model, size and USB bus. Inspect full details:' -ForegroundColor Green
    $target | Format-List
    Write-Host '[IMPORTANT] Cross-check PnP chain with ORICO VIA Labs 2109:0715 in USBView.' -ForegroundColor Yellow
    Write-Host '[IMPORTANT] USBView speed is a manually observed fact, not established by Get-Disk.' -ForegroundColor Yellow
    Write-Host '[INFO] For a full read-only experiment, specify these verified numbers explicitly:'
    Write-Host ('  --disk '+$target.Number+' --size '+$target.GetDiskSize+' --win32-size '+$target.Win32Size+' --letter '+$target.Letters)
}
Write-Host '[INFO] Preflight completed; no physical disk sectors read, no files written.'
