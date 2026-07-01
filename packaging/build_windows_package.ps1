$ErrorActionPreference = "Stop"

function Join-UnicodeChars([int[]] $Codes) {
  $Chars = foreach ($Code in $Codes) { [char] $Code }
  return -join $Chars
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$AppName = Join-UnicodeChars @(0x5fd7, 0x613f, 0x843d, 0x70b9, 0x6982, 0x7387, 0x4f30, 0x7b97, 0x5668)
$RunText = Join-UnicodeChars @(0x8fd0, 0x884c)
$UseText = Join-UnicodeChars @(0x4f7f, 0x7528, 0x8bf4, 0x660e)

$SpecPath = Join-Path $Root ($AppName + ".spec")
if (!(Test-Path $SpecPath)) {
  $SpecPath = Get-ChildItem -Path $Root -File -Filter "*.spec" |
    Where-Object { $_.Name -notlike "zytb*" } |
    Select-Object -First 1 -ExpandProperty FullName
}
if (!$SpecPath -or !(Test-Path $SpecPath)) {
  throw "PyInstaller spec file was not found."
}

$PackageDir = Join-Path $Root ("dist\" + $AppName)
$ZipPath = Join-Path $Root ("dist\" + $AppName + "_windows.zip")
$RunBatName = $RunText + "_" + $AppName + ".bat"
$ReadmeName = "README_" + $UseText + ".txt"
$ReadmeSource = Join-Path $Root ("packaging\" + $ReadmeName)

python -m PyInstaller $SpecPath --clean --noconfirm

if (!(Test-Path $PackageDir)) {
  throw "Package directory was not created: $PackageDir"
}

Copy-Item "packaging\run_estimator.bat" (Join-Path $PackageDir $RunBatName) -Force
Copy-Item "packaging\run_estimator.bat" (Join-Path $PackageDir "run_estimator.bat") -Force
if (Test-Path $ReadmeSource) {
  Copy-Item $ReadmeSource (Join-Path $PackageDir $ReadmeName) -Force
}

if (Test-Path $ZipPath) {
  Remove-Item $ZipPath -Force
}

Compress-Archive -Path $PackageDir -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "Windows package created:"
Write-Host $PackageDir
Write-Host $ZipPath
Write-Host ""
Write-Host "Share the zip file, or share the whole package directory."
Write-Host ("End users should double-click: " + $RunBatName)
