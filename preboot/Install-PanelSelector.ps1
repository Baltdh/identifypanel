param(
    [Parameter(Mandatory = $true)]
    [string]$BootRoot,
    [string]$R36HOriginalOverlay,
    [switch]$ConfirmLegacyUboot
)

$ErrorActionPreference = "Stop"
function Fail([string]$Message) { throw "IdentifyPanel: $Message" }

function Test-FdtMagic([string]$Path) {
    if (!(Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $Stream = [System.IO.File]::OpenRead($Path)
    try {
        if ($Stream.Length -lt 40) { return $false }
        $Header = New-Object byte[] 4
        if ($Stream.Read($Header, 0, 4) -ne 4) { return $false }
        return ($Header[0] -eq 0xD0 -and $Header[1] -eq 0x0D -and $Header[2] -eq 0xFE -and $Header[3] -eq 0xED)
    }
    finally {
        $Stream.Dispose()
    }
}

$BootRoot = (Resolve-Path -LiteralPath $BootRoot).Path
$BootScr = Join-Path $BootRoot "boot.scr"
$BootIni = Join-Path $BootRoot "boot.ini"
$SavedBootScr = Join-Path $BootRoot "boot0.scr"
$UpdateLog = Join-Path $BootRoot "update.log"
$Extlinux = Join-Path $BootRoot "extlinux\extlinux.conf"
$OverlayDir = Join-Path $BootRoot "overlays"
$PanelDir = Join-Path $BootRoot "IPANEL"
$PackageRoot = Split-Path -Parent $PSScriptRoot
$SelectorScr = Join-Path $PSScriptRoot "PanelSelector.scr"
$OfficialProfiles = Join-Path $PackageRoot "profiles\official"

if (!(Test-Path -LiteralPath $BootScr -PathType Leaf)) { Fail "boot.scr nao foi encontrado na particao indicada." }
if (Test-Path -LiteralPath $BootIni) { Fail "boot.ini existe e tem prioridade sobre boot.scr. Nao vou alterar o fluxo sem inspecao." }
if (!(Test-Path -LiteralPath $Extlinux -PathType Leaf)) { Fail "extlinux\extlinux.conf nao foi encontrado. Este beta exige ROCKNIX RK3326." }
$ExtlinuxText = Get-Content -LiteralPath $Extlinux -Raw
if ($ExtlinuxText -notmatch '(?m)^\s*FDTOVERLAYS\s+/overlays/mipi-panel\.dtbo\s*$') {
    Fail "extlinux.conf nao aponta para /overlays/mipi-panel.dtbo; instalacao cancelada."
}
$FdtMatches = [regex]::Matches($ExtlinuxText, '(?m)^\s*FDT\s+(/[^#\s]+\.dtb)\s*$')
if ($FdtMatches.Count -ne 1) {
    Fail "R36H exige exatamente uma diretiva FDT explicita em extlinux.conf."
}
$FdtRelative = $FdtMatches[0].Groups[1].Value.TrimStart("/") -replace "/", [System.IO.Path]::DirectorySeparatorChar
$FdtPath = Join-Path $BootRoot $FdtRelative
if (!(Test-Path -LiteralPath $FdtPath -PathType Leaf)) {
    Fail "O DTB base indicado por FDT nao existe na particao: $FdtRelative"
}
if (!(Test-Path -LiteralPath $SelectorScr -PathType Leaf)) { Fail "PanelSelector.scr nao foi gerado pelo pacote de build." }
if (!(Test-Path -LiteralPath $OfficialProfiles -PathType Container)) { Fail "profiles\official nao foi encontrado dentro do pacote." }

$LegacyConfirmed = $false
if (Test-Path -LiteralPath $UpdateLog -PathType Leaf) {
    $LogText = Get-Content -LiteralPath $UpdateLog -Raw
    if ($LogText -match '(?i)Using legacy u-boot') { $LegacyConfirmed = $true }
    if ($LogText -match '(?i)b_uboot\.bin|Cannot find UART console|Assuming default \(UART') {
        Fail "update.log indica U-Boot variante B/mainline. Este seletor e somente para U-Boot legado A."
    }
}
if (!$LegacyConfirmed -and !$ConfirmLegacyUboot) {
    Fail "Nao consegui confirmar U-Boot legado A. Use -ConfirmLegacyUboot somente apos verificar que a imagem e a variante A."
}
if (Test-Path -LiteralPath $SavedBootScr) { Fail "boot0.scr ja existe. Nao vou sobrescrever o backup anterior." }

$ProfileMap = @{
    "mipi-panel.dtbo.r36s-panel1" = "PANEL1.DTBO"
    "mipi-panel.dtbo.r36s-panel2" = "PANEL2.DTBO"
    "mipi-panel.dtbo.r36s-panel3" = "PANEL3.DTBO"
    "mipi-panel.dtbo.r36s-panel4" = "PANEL4.DTBO"
    "mipi-panel.dtbo.r36s_clone" = "CLONE.DTBO"
    "mipi-panel.dtbo.rg351mp-v2" = "351MP.DTBO"
}
foreach ($SourceName in $ProfileMap.Keys) {
    $SourcePath = Join-Path $OfficialProfiles $SourceName
    if (!(Test-Path -LiteralPath $SourcePath -PathType Leaf)) { Fail "Perfil oficial ausente: $SourceName" }
}

if ($R36HOriginalOverlay) {
    $OriginalPath = (Resolve-Path -LiteralPath $R36HOriginalOverlay).Path
    if (!(Test-FdtMagic $OriginalPath)) {
        Fail "O arquivo indicado para R36H nao possui assinatura FDT/DTBO. Um DTB bruto nao e um overlay."
    }
}

$ActiveOverlay = Join-Path $OverlayDir "mipi-panel.dtbo"
$PanelBase = Join-Path $PanelDir "BASE.DTBO"
if (!(Test-Path -LiteralPath $PanelBase -PathType Leaf)) {
    if (Test-Path -LiteralPath $ActiveOverlay -PathType Leaf) {
        if (!(Test-FdtMagic $ActiveOverlay)) { Fail "O overlay ativo nao possui assinatura FDT; backup recusado." }
    }
    elseif (!$R36HOriginalOverlay) {
        Fail "Nao existe overlay ativo. Informe -R36HOriginalOverlay com o DTBO importado a partir do DTB que funcionava."
    }
}

New-Item -ItemType Directory -Path $PanelDir -Force | Out-Null
New-Item -ItemType Directory -Path $OverlayDir -Force | Out-Null

foreach ($SourceName in $ProfileMap.Keys) {
    $DestinationName = $ProfileMap[$SourceName]
    Copy-Item -LiteralPath (Join-Path $OfficialProfiles $SourceName) -Destination (Join-Path $PanelDir $DestinationName) -Force
}

if ($R36HOriginalOverlay) {
    Copy-Item -LiteralPath $OriginalPath -Destination (Join-Path $PanelDir "R36H.DTBO") -Force
}

if (!(Test-Path -LiteralPath $PanelBase -PathType Leaf)) {
    if (Test-Path -LiteralPath $ActiveOverlay -PathType Leaf) {
        Copy-Item -LiteralPath $ActiveOverlay -Destination $PanelBase
    }
    else {
        Copy-Item -LiteralPath (Join-Path $PanelDir "R36H.DTBO") -Destination $PanelBase
    }
}

# A troca do boot.scr so ocorre depois de todos os arquivos e backups estarem prontos.
Copy-Item -LiteralPath $BootScr -Destination $SavedBootScr
try {
    Copy-Item -LiteralPath $SelectorScr -Destination $BootScr -Force
}
catch {
    Copy-Item -LiteralPath $SavedBootScr -Destination $BootScr -Force
    throw
}

Write-Host "IdentifyPanel PreBoot instalado."
Write-Host "Original preservado em: $SavedBootScr"
Write-Host "Menu: segure R1 ao ligar; escolha uma tecla quando o menu aparecer."
Write-Host "Para remover, execute Restore-Original-Boot.ps1 com o mesmo BootRoot."
Write-Warning "Mapa de botoes vem de referencia R36S e ainda nao foi confirmado na sua revisao R36H."
Write-Warning "A tela do menu depende do U-Boot legado conseguir inicializar o LCD antes do kernel."
