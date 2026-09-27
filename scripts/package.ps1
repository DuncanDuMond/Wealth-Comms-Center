param([string]$Destination)
$ErrorActionPreference = 'Stop'
$wealthSource = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $Destination) {
    $Destination = Join-Path (Split-Path -Parent $wealthSource) 'wealth-command-center-source.zip'
}
$wealthTarget = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $wealthTarget) { throw 'Destination already exists; choose a new archive name.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$wealthFiles = @(Get-ChildItem -LiteralPath $wealthSource -File -Force | Where-Object { $_.Name -ne '.env' })
foreach ($wealthPart in @('wealth_command_center','vendor','web','registry','docs','tests','scripts','.github')) {
    $wealthFolder = Join-Path $wealthSource $wealthPart
    if (Test-Path -LiteralPath $wealthFolder) {
        $wealthFiles += Get-ChildItem -LiteralPath $wealthFolder -File -Recurse -Force |
            Where-Object { $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc' }
    }
}
$wealthArchive = [IO.Compression.ZipFile]::Open($wealthTarget, [IO.Compression.ZipArchiveMode]::Create)
try {
    foreach ($wealthFile in $wealthFiles) {
        $wealthEntry = $wealthFile.FullName.Substring($wealthSource.Length + 1).Replace('\','/')
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($wealthArchive, $wealthFile.FullName, "wealth-command-center/$wealthEntry") | Out-Null
    }
} finally { $wealthArchive.Dispose() }
Write-Host "Packaged $($wealthFiles.Count) source files. No database, credentials, virtual environment or test screenshots included."
Get-Item -LiteralPath $wealthTarget | Select-Object FullName,Length
