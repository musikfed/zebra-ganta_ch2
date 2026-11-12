param(
    [int]$DiskNumber = 2,
    [string]$ExpectedModel = 'HTS725050B7E630',
    [string]$ExpectedDriveLetter = 'T'
)
# Zebra Ganta USB bridge inspector v1. Read-only CIM/PnP inventory.
# Does NOT read raw disk sectors, change drivers, write to disk or infer USB speed.
$ErrorActionPreference = 'Stop'
function Label([string]$k, $v) {
    Write-Host ('{0,-27} {1}' -f $k, [string]$v)
}
function OptionalProperty([string]$instanceId, [string]$keyName) {
    try {
        $p=Get-PnpDeviceProperty -InstanceId $instanceId -KeyName $keyName -ErrorAction Stop
        return $p.Data
    } catch { return $null }
}
Write-Host '=== Zebra Ganta: HGST USB Bridge Inspector v1 ===' -ForegroundColor Cyan
$disk = Get-Disk -Number $DiskNumber -ErrorAction Stop
$wmi = Get-CimInstance Win32_DiskDrive -Filter "Index=$DiskNumber" -ErrorAction Stop
if(!$wmi){throw 'No Win32_DiskDrive found for this number.'}
$actualName=([string]$disk.FriendlyName)+' '+([string]$wmi.Model)
if(($actualName -replace '[^A-Za-z0-9]','').ToUpperInvariant() -notlike ('*'+(($ExpectedModel -replace '[^A-Za-z0-9]','').ToUpperInvariant())+'*')){
    throw ('Disk model mismatch: '+$actualName+'. No other device is selected.')
}
if($disk.BusType.ToString() -ne 'USB'){throw ('Disk is not USB: '+$disk.BusType)}
if($disk.IsBoot -or $disk.IsSystem){throw 'Refusing system/boot disk.'}
$partitions=@(Get-Partition -DiskNumber $DiskNumber -ErrorAction Stop)
$letters=@($partitions | Where-Object {$_.DriveLetter} | ForEach-Object {$_.DriveLetter.ToString().ToUpperInvariant()})
if($letters -notcontains $ExpectedDriveLetter.ToUpperInvariant()){
    throw ('Drive letter mismatch: expected '+$ExpectedDriveLetter+':, got '+($letters -join ',')+'.')
}
Label 'Disk number' $DiskNumber
Label 'Disk model' $wmi.Model
Label 'Get-Disk FriendlyName' $disk.FriendlyName
Label 'Windows BusType' $disk.BusType
Label 'Get-Disk bytes' $disk.Size
Label 'Win32_DiskDrive bytes' $wmi.Size
Label 'Drive letters' ($letters -join ', ')
Label 'InterfaceType (WMI)' $wmi.InterfaceType
Label 'PNPDeviceID' $wmi.PNPDeviceID
Write-Host ''
Write-Host '--- PnP ancestor chain (best effort) ---' -ForegroundColor Cyan
$current=[string]$wmi.PNPDeviceID
$visited=@{}
for($i=0;$i -lt 12 -and $current;$i++){
    if($visited.ContainsKey($current)){break}
    $visited[$current]=$true
    $node=$null
    try {$node=Get-PnpDevice -InstanceId $current -ErrorAction Stop} catch {}
    Label ('Level '+$i) $current
    if($node){Label '  FriendlyName' $node.FriendlyName;Label '  Class' $node.Class;Label '  Status' $node.Status}
    $busReported=OptionalProperty $current 'DEVPKEY_Device_BusReportedDeviceDesc'
    if($busReported){Label '  Bus description' $busReported}
    $parent=OptionalProperty $current 'DEVPKEY_Device_Parent'
    if(!$parent){Write-Host '[INFO] Parent relationship unavailable from PnP properties; chain ends.';break}
    if($parent -is [array]){$parent=$parent[0]}
    $current=[string]$parent
}
Write-Host ''
Write-Host '--- Interpretation ---' -ForegroundColor Cyan
Write-Host '[OK] Read-only Windows disk/PnP inventory collected.'
Write-Host '[INFO] Windows BusType=USB and USB device IDs do NOT establish negotiated USB speed.'
Write-Host '[INFO] Open USBView x64; select the USB Mass Storage / JMicron device.'
Write-Host '[INFO] Copy: Connection Information V2 -> Device Bus Speed and Supported USB Protocols;'
Write-Host '       also inspect Device Descriptor -> idVendor and idProduct.'
Write-Host '[INFO] High-Speed (480 Mb/s) vs SuperSpeed (5 Gb/s) must come from USBView or equivalent.'
Write-Host '[INFO] This did not access \\.\PhysicalDrive2, send SMART commands, or write to T:.'
