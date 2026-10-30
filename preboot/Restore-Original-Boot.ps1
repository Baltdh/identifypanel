param(
    [Parameter(Mandatory = $true)]
    [string]$BootRoot
)
$ErrorActionPreference = "Stop"
$BootRoot = (Resolve-Path -LiteralPath $BootRoot).Path
$BootScr = Join-Path $BootRoot "boot.scr"
$SavedBootScr = Join-Path $BootRoot "boot0.scr"
if (!(Test-Path -LiteralPath $SavedBootScr -PathType Leaf)) { throw "IdentifyPanel: boot0.scr nao foi encontrado; backup original indisponivel." }
Copy-Item -LiteralPath $SavedBootScr -Destination $BootScr -Force
Write-Host "Boot original restaurado em $BootScr"
Write-Host "boot0.scr foi mantido como backup."
