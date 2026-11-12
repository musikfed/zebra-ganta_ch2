param([switch]$BuildTest)
# PEGINELAB Windows SDK Doctor v7: read-only. Windows PowerShell 5.1+.
# No downloads, registry edits, PATH modifications or installation.
# Optional -BuildTest creates a tiny C source/EXE in TEMP and removes it afterward.
$ErrorActionPreference = 'Continue'
Write-Host '=== PEGINELAB Windows SDK Doctor v7 ===' -ForegroundColor Cyan
Write-Host ('Windows: ' + [Environment]::OSVersion.VersionString)
Write-Host ('PowerShell: ' + $PSVersionTable.PSVersion)
Write-Host ('Architecture x64 OS: ' + [Environment]::Is64BitOperatingSystem)
Write-Host ('User: ' + [Environment]::UserName)
function Report($level,$label,$value) {
  $color = if($level -eq 'OK') {'Green'} elseif($level -eq 'WARN') {'Yellow'} else {'Gray'}
  Write-Host ('['+$level+'] '+$label+': '+$value) -ForegroundColor $color
}
function RunCommand($executable,[string[]]$arguments) {
  try {
    $output = & $executable @arguments 2>&1 | Out-String
    return @{Exit=$LASTEXITCODE;Text=$output.Trim()}
  } catch {return @{Exit=-1;Text=$_.Exception.Message}}
}
$roots = New-Object 'System.Collections.Generic.List[string]'
foreach($key in @('HKLM:\SOFTWARE\Microsoft\Windows Kits\Installed Roots','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows Kits\Installed Roots')) {
  if(Test-Path $key) {
    $record=Get-ItemProperty $key -ErrorAction SilentlyContinue
    foreach($name in @('KitsRoot10','KitsRoot81')) {
      if($record -and $record.$name){$normalized=$record.$name.TrimEnd('\');if(!$roots.Contains($normalized)){$roots.Add($normalized)}}
    }
  }
}
foreach($candidate in @(
  'C:\Program Files (x86)\Windows Kits\10',
  'F:\WindowsKits\10','T:\WindowsKits\10',
  'F:\Program Files (x86)\Windows Kits\10','T:\Program Files (x86)\Windows Kits\10'
)) {
  $normalized=$candidate.TrimEnd('\');if((Test-Path -LiteralPath $normalized) -and !$roots.Contains($normalized)){$roots.Add($normalized)}
}
Write-Host ''
Write-Host '--- WINDOWS SDK ---' -ForegroundColor Cyan
if($roots.Count -eq 0){Report WARN 'SDK' 'Registry and common paths contain no Windows Kits root'}
$hasHeaders=$false; $hasLibs=$false
foreach($root in $roots) {
  if(!(Test-Path -LiteralPath $root)){Report WARN 'Registered SDK root missing' $root;continue}
  Report INFO 'SDK directory exists (not proof of installation)' $root
  $versions = @(Get-ChildItem -LiteralPath (Join-Path $root 'Include') -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending)
  if($versions.Count -eq 0) {Report WARN 'SDK include versions' 'No Include\version directories. SDK may have been downloaded but not installed.'}
  foreach($v in $versions){
    $header=Join-Path $v.FullName 'um\Windows.h'
    $lib=Join-Path (Join-Path $root 'Lib') ($v.Name+'\um\x64\kernel32.lib')
    $headerPresent=Test-Path -LiteralPath $header
    $libPresent=Test-Path -LiteralPath $lib
    if($headerPresent){$hasHeaders=$true}
    if($libPresent){$hasLibs=$true}
    Report $(if($headerPresent -and $libPresent){'OK'}else{'WARN'}) ('SDK '+$v.Name) ('Windows.h='+$headerPresent+'; x64 kernel32.lib='+$libPresent)
  }
  foreach($tool in @('signtool.exe','wpa.exe','windbg.exe','usbview.exe')){
    $hits=@(Get-ChildItem -LiteralPath $root -File -Recurse -Filter $tool -ErrorAction SilentlyContinue | Select-Object -First 2 -ExpandProperty FullName)
    foreach($hit in $hits){Report OK $tool $hit}
  }
}
if(!$hasHeaders -or !$hasLibs){Report WARN 'SDK development capability' 'Windows.h / kernel32.lib not confirmed. SDK may be incomplete or not installed.'}
Write-Host ''
Write-Host '--- VISUAL STUDIO BUILD TOOLS ---' -ForegroundColor Cyan
$pf86=[Environment]::GetFolderPath('ProgramFilesX86')
$vswhere=Join-Path $pf86 'Microsoft Visual Studio\Installer\vswhere.exe'
$vsPath=$null
if(Test-Path -LiteralPath $vswhere){
  $res=RunCommand $vswhere @('-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath')
  if($res.Exit -eq 0 -and $res.Text){$vsPath=($res.Text -split "[\r\n]+" | Select-Object -First 1).Trim();Report OK 'Visual Studio C++ toolset installation' $vsPath}
  else {
    Report WARN 'C++ toolset' 'vswhere did not find a complete VC.Tools.x86.x64 component'
    $fallback=RunCommand $vswhere @('-latest','-products','*','-property','installationPath')
    if($fallback.Exit -eq 0 -and $fallback.Text){$vsPath=($fallback.Text -split "[\r\n]+" | Select-Object -First 1).Trim();Report INFO 'Visual Studio installation' $vsPath}
  }
} else {Report WARN 'vswhere.exe' 'Not found'}
$devcmd=$null
if($vsPath){$devcmd=Join-Path $vsPath 'Common7\Tools\VsDevCmd.bat'}
if($devcmd -and (Test-Path -LiteralPath $devcmd)){
  Report OK 'VsDevCmd.bat present' $devcmd
  Report INFO 'MSVC shell environment' 'Use the installed x64 Native Tools Command Prompt to activate headers, libraries and PATH'
} else {Report WARN 'VsDevCmd.bat' 'Not found; inspect Build Tools workloads'}
if($vsPath){
  $vcRoot=Join-Path $vsPath 'VC\Tools\MSVC'
  $compilers=@(Get-ChildItem -LiteralPath $vcRoot -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | ForEach-Object {
    Join-Path $_.FullName 'bin\Hostx64\x64\cl.exe'
  } | Where-Object {Test-Path -LiteralPath $_})
  if($compilers.Count -gt 0){
    $clPath=$compilers[0]
    Report OK 'MSVC x64 compiler file' $clPath
    # cl /Bv without an input file can return nonzero even though cl.exe works.
    # Detect the compiler banner but do not call this a successful C++ build.
    $v=RunCommand $clPath @('/Bv')
    if($v.Text -match 'C/C\+\+ Optimizing Compiler Version'){
      $banner=($v.Text -split "[\r\n]+" | Where-Object {$_ -match 'C/C\+\+ Optimizing Compiler Version'} | Select-Object -First 1)
      Report OK 'MSVC compiler version detected' $banner.Trim()
      Report INFO 'C++ compilation' 'Not tested; /Bv without a source file may exit 2. Windows SDK headers/libraries must be available for WinAPI builds.'
    }else{
      Report WARN 'MSVC executable response' ('Exit '+$v.Exit+'; '+($v.Text -split "[\r\n]+" | Select-Object -First 2))
    }
  } else {Report WARN 'MSVC x64 compiler' 'No cl.exe under VC\Tools\MSVC; install C++ build tools workload'}
}
Write-Host ''
Write-Host '--- PYTHON AND OTHER TOOLS ---' -ForegroundColor Cyan
foreach($name in @('python','py','uv','git','cl','link','signtool','wpr','wpa','windbg','usbview')){
  $cmd=Get-Command $name -ErrorAction SilentlyContinue
  if($cmd){
    $value=$cmd.Source
    if($name -eq 'python' -and $value -match 'WindowsApps'){Report INFO $name ('WindowsApps execution alias; verify actual interpreter below: '+$value)}
    elseif($name -eq 'cl' -or $name -eq 'link'){Report INFO $name ('Current PATH: '+$value+' (Developer Prompt is preferred)')}
    else {Report OK $name $value}
  } else {
    if($name -eq 'cl' -or $name -eq 'link'){Report INFO $name 'Not in current PowerShell PATH; normal outside VS Developer Prompt'}
    else{Report INFO $name 'Not in current PATH (may be installed elsewhere)'}
  }
}
$py=RunCommand 'python' @('-c','import sys; print(sys.executable); print(sys.version.split()[0])')
if($py.Exit -eq 0){Report OK 'Python runtime' $py.Text.Replace([Environment]::NewLine,' | ')}
else{Report WARN 'python -c' 'Runtime not confirmed; check uv run python --version or py -0p'}
if(Get-Command 'uv' -ErrorAction SilentlyContinue){
  $u=RunCommand 'uv' @('python','list','--only-installed')
  if($u.Exit -eq 0){Report INFO 'uv installed Python interpreters' $u.Text}
}
Write-Host ''
Write-Host '=== Summary ===' -ForegroundColor Cyan
if($hasHeaders -and $hasLibs){Report OK 'SDK x64 headers/libraries' 'Available'}
else{Report WARN 'SDK x64 headers/libraries' 'Not verified'}
Report INFO 'USBView' 'Optional diagnostic utility. SDK may be installed with only some features; check installer component selections.'
Report INFO 'Security' 'Default checks read-only; -BuildTest only writes disposable files in TEMP, never on HGST T:'

Write-Host ''
Write-Host '--- OPTIONAL REAL WINAPI BUILD ---' -ForegroundColor Cyan
if(!$BuildTest){
  Report INFO 'Compile/run smoke test' 'Not run. To test: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\windows-sdk-doctor.ps1 -BuildTest'
} elseif(!$devcmd -or !(Test-Path -LiteralPath $devcmd)){
  Report WARN 'Compile/run smoke test' 'VsDevCmd.bat missing'
} elseif(!$hasHeaders -or !$hasLibs){
  Report WARN 'Compile/run smoke test' 'SDK x64 Windows.h/kernel32.lib missing. No build attempted.'
} elseif(([System.IO.Path]::GetPathRoot([System.IO.Path]::GetFullPath($env:TEMP))).TrimEnd('\\') -ieq 'T:'){
  Report WARN 'Compile/run smoke test' 'TEMP points to HDD under test (T:); refusing to write test files.'
} else {
  # All generated files remain in a unique temporary directory, not on the HDD under test.
  $work=Join-Path $env:TEMP ('peginelab-sdk-smoke-'+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $work -ErrorAction Stop | Out-Null
  try {
    $sourcePath=Join-Path $work 'sdk_smoke.c'
    $exePath=Join-Path $work 'sdk_smoke.exe'
    $cmdPath=Join-Path $work 'build.cmd'
    @'
#include <windows.h>
#include <stdio.h>
int main(void) {
  printf("PEGINELAB_SDK_OK pid=%lu\n", (unsigned long)GetCurrentProcessId());
  return 0;
}
'@ | Set-Content -LiteralPath $sourcePath -Encoding Ascii
    $vcvars=Join-Path $vsPath 'VC\Auxiliary\Build\vcvars64.bat'
    $setupScript=if(Test-Path -LiteralPath $vcvars){$vcvars}else{$devcmd}
    Report INFO 'Build environment batch' $setupScript
    $setupArgs=if($setupScript -eq $devcmd){' -arch=amd64 -host_arch=amd64'}else{''}
    # Format each line as ONE string: PowerShell array parsing with '+' previously
    # fragmented the quoted VS path into separate batch commands.
    $cmdLines=@(
      '@echo off'
      ('call "{0}"{1}' -f $setupScript,$setupArgs)
      'if errorlevel 1 exit /b 11'
      ('cd /d "{0}"' -f $work)
      ('cl.exe /nologo /W3 /TC "{0}" /link /OUT:"{1}"' -f $sourcePath,$exePath)
      'exit /b %errorlevel%'
    )
    $cmdLines | Set-Content -LiteralPath $cmdPath -Encoding Ascii
    Report INFO 'Generated batch command count' $cmdLines.Count
    # Avoid cmd.exe nested quoting entirely: launch build.cmd from its own
    # temporary working directory. Quoted paths inside build.cmd are safe.
    Push-Location -LiteralPath $work
    try {
      $output=& $env:ComSpec /d /c 'build.cmd' 2>&1 | Out-String
      $rc=$LASTEXITCODE
    } finally { Pop-Location }
    if($rc -eq 0 -and (Test-Path -LiteralPath $exePath)){
      $appOutput=& $exePath 2>&1 | Out-String
      if($LASTEXITCODE -eq 0 -and $appOutput -match 'PEGINELAB_SDK_OK'){
        Report OK 'Real WinAPI compile/link/run' $appOutput.Trim()
      }else{Report WARN 'Built program execution' $appOutput.Trim()}
    }else{
      Report WARN 'Real WinAPI compile/link' ('Exit='+$rc)
      Write-Host $output
    }
  } catch {Report WARN 'Build test exception' $_.Exception.Message}
  finally {
    if(Test-Path -LiteralPath $work){
      Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}
