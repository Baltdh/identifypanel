param(
    [Parameter(Mandatory = $true)]
    [string]$BootRoot,
    [string]$R36HOriginalOverlay,
    [switch]$ConfirmLegacyUboot
)
$ErrorActionPreference = "Stop"
function Fail([string]$Message) { throw "IdentifyPanel: $Message" }

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
if (!(Test-Path -LiteralPath $Extlinux -PathType Leaf)) { Fail "extlinux\extlinux.conf nao foi encontrado. Este beta exige o fluxo ROCKNIX RK3326 A." }
$ExtlinuxText = Get-Content -LiteralPath $Extlinux -Raw
if ($ExtlinuxText -notmatch '(?m)^\s*FDTOVERLAYS\s+/overlays/mipi-panel\.dtbo\s*if (!(Test-Path -LiteralPath $SelectorScr -PathType Leaf)) { Fail "PanelSelector.scr nao foi gerado pelo pacote de build." }
if (!(Test-Path -LiteralPath $OfficialProfiles -PathType Container)) { Fail "profiles\official nao foi encontrado dentro do pacote." }

$LegacyConfirmed = $false
if (Test-Path -LiteralPath $UpdateLog -PathType Leaf) {
    $LogText = Get-Content -LiteralPath $UpdateLog -Raw
    if ($LogText -match '(?i)Using legacy u-boot') { $LegacyConfirmed = $true }
    if ($LogText -match '(?i)b_uboot\.bin|Cannot find UART console|Assuming default \(UART') { Fail "update.log indica U-Boot variante B/mainline. Este seletor e somente para U-Boot legado A." }
}
if (!$LegacyConfirmed -and !$ConfirmLegacyUboot) { Fail "Nao consegui confirmar U-Boot legado A. Use -ConfirmLegacyUboot somente apos verificar que a imagem e a variante A." }
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

New-Item -ItemType Directory -Path $PanelDir -Force | Out-Null
New-Item -ItemType Directory -Path $OverlayDir -Force | Out-Null
foreach ($SourceName in $ProfileMap.Keys) {
    $DestinationName = $ProfileMap[$SourceName]
    Copy-Item -LiteralPath (Join-Path $OfficialProfiles $SourceName) -Destination (Join-Path $PanelDir $DestinationName) -Force
}

if ($R36HOriginalOverlay) {
    $OriginalPath = (Resolve-Path -LiteralPath $R36HOriginalOverlay).Path
    if (!(Test-Path -LiteralPath $OriginalPath -PathType Leaf)) { Fail "O overlay original R36H indicado nao e um arquivo." }
    $Header = [System.IO.File]::ReadAllBytes($OriginalPath)
    if ($Header.Length -lt 40 -or $Header[0] -ne 0xD0 -or $Header[1] -ne 0x0D -or $Header[2] -ne 0xFE -or $Header[3] -ne 0xED) { Fail "O arquivo indicado para R36H nao possui assinatura FDT/DTBO. Um DTB bruto nao e um overlay." }
    Copy-Item -LiteralPath $OriginalPath -Destination (Join-Path $PanelDir "R36H.DTBO") -Force
}

$Baseline = Join-Path $PanelDir "BASE.DTBO"
if (!(Test-Path -LiteralPath $Baseline -PathType Leaf)) {
    $ActiveOverlay = Join-Path $OverlayDir "mipi-panel.dtbo"
    if (Test-Path -LiteralPath $ActiveOverlay -PathType Leaf) {
        Copy-Item -LiteralPath $ActiveOverlay -Destination $Baseline
    }
    elseif (Test-Path -LiteralPath (Join-Path $PanelDir "R36H.DTBO") -PathType Leaf) {
        Copy-Item -LiteralPath (Join-Path $PanelDir "R36H.DTBO") -Destination $Baseline
    }
    else {
        Fail "Nao existe overlay ativo nem R36H.DTBO. Prepare o overlay original antes de instalar o seletor."
    }
}

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
) { Fail "extlinux.conf nao aponta para /overlays/mipi-panel.dtbo; instalacao cancelada." }
if ($ExtlinuxText -notmatch '(?m)^\s*FDT\s+(/[^#\s]+\.dtb)\s*if (!(Test-Path -LiteralPath $SelectorScr -PathType Leaf)) { Fail "PanelSelector.scr nao foi gerado pelo pacote de build." }
if (!(Test-Path -LiteralPath $OfficialProfiles -PathType Container)) { Fail "profiles\official nao foi encontrado dentro do pacote." }

$LegacyConfirmed = $false
if (Test-Path -LiteralPath $UpdateLog -PathType Leaf) {
    $LogText = Get-Content -LiteralPath $UpdateLog -Raw
    if ($LogText -match '(?i)Using legacy u-boot') { $LegacyConfirmed = $true }
    if ($LogText -match '(?i)b_uboot\.bin|Cannot find UART console|Assuming default \(UART') { Fail "update.log indica U-Boot variante B/mainline. Este seletor e somente para U-Boot legado A." }
}
if (!$LegacyConfirmed -and !$ConfirmLegacyUboot) { Fail "Nao consegui confirmar U-Boot legado A. Use -ConfirmLegacyUboot somente apos verificar que a imagem e a variante A." }
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

New-Item -ItemType Directory -Path $PanelDir -Force | Out-Null
New-Item -ItemType Directory -Path $OverlayDir -Force | Out-Null
foreach ($SourceName in $ProfileMap.Keys) {
    $DestinationName = $ProfileMap[$SourceName]
    Copy-Item -LiteralPath (Join-Path $OfficialProfiles $SourceName) -Destination (Join-Path $PanelDir $DestinationName) -Force
}

if ($R36HOriginalOverlay) {
    $OriginalPath = (Resolve-Path -LiteralPath $R36HOriginalOverlay).Path
    if (!(Test-Path -LiteralPath $OriginalPath -PathType Leaf)) { Fail "O overlay original R36H indicado nao e um arquivo." }
    Copy-Item -LiteralPath $OriginalPath -Destination (Join-Path $PanelDir "R36H.DTBO") -Force
}

$Baseline = Join-Path $PanelDir "BASE.DTBO"
if (!(Test-Path -LiteralPath $Baseline -PathType Leaf)) {
    $ActiveOverlay = Join-Path $OverlayDir "mipi-panel.dtbo"
    if (Test-Path -LiteralPath $ActiveOverlay -PathType Leaf) {
        Copy-Item -LiteralPath $ActiveOverlay -Destination $Baseline
    }
    elseif (Test-Path -LiteralPath (Join-Path $PanelDir "R36H.DTBO") -PathType Leaf) {
        Copy-Item -LiteralPath (Join-Path $PanelDir "R36H.DTBO") -Destination $Baseline
    }
    else {
        Fail "Nao existe overlay ativo nem R36H.DTBO. Prepare o overlay original antes de instalar o seletor."
    }
}

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
) { Fail "R36H exige FDT explicito em extlinux.conf. Prepare o DTB base no PC antes de instalar o seletor." }
$FdtRelative = $Matches[1].TrimStart("/") -replace "/", "\"
$FdtPath = Join-Path $BootRoot $FdtRelative
if (!(Test-Path -LiteralPath $FdtPath -PathType Leaf)) { Fail "O DTB base indicado por FDT nao existe na particao: $FdtRelative" }
if (!(Test-Path -LiteralPath $SelectorScr -PathType Leaf)) { Fail "PanelSelector.scr nao foi gerado pelo pacote de build." }
if (!(Test-Path -LiteralPath $OfficialProfiles -PathType Container)) { Fail "profiles\official nao foi encontrado dentro do pacote." }

$LegacyConfirmed = $false
if (Test-Path -LiteralPath $UpdateLog -PathType Leaf) {
    $LogText = Get-Content -LiteralPath $UpdateLog -Raw
    if ($LogText -match '(?i)Using legacy u-boot') { $LegacyConfirmed = $true }
    if ($LogText -match '(?i)b_uboot\.bin|Cannot find UART console|Assuming default \(UART') { Fail "update.log indica U-Boot variante B/mainline. Este seletor e somente para U-Boot legado A." }
}
if (!$LegacyConfirmed -and !$ConfirmLegacyUboot) { Fail "Nao consegui confirmar U-Boot legado A. Use -ConfirmLegacyUboot somente apos verificar que a imagem e a variante A." }
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

New-Item -ItemType Directory -Path $PanelDir -Force | Out-Null
New-Item -ItemType Directory -Path $OverlayDir -Force | Out-Null
foreach ($SourceName in $ProfileMap.Keys) {
    $DestinationName = $ProfileMap[$SourceName]
    Copy-Item -LiteralPath (Join-Path $OfficialProfiles $SourceName) -Destination (Join-Path $PanelDir $DestinationName) -Force
}

if ($R36HOriginalOverlay) {
    $OriginalPath = (Resolve-Path -LiteralPath $R36HOriginalOverlay).Path
    if (!(Test-Path -LiteralPath $OriginalPath -PathType Leaf)) { Fail "O overlay original R36H indicado nao e um arquivo." }
    Copy-Item -LiteralPath $OriginalPath -Destination (Join-Path $PanelDir "R36H.DTBO") -Force
}

$Baseline = Join-Path $PanelDir "BASE.DTBO"
if (!(Test-Path -LiteralPath $Baseline -PathType Leaf)) {
    $ActiveOverlay = Join-Path $OverlayDir "mipi-panel.dtbo"
    if (Test-Path -LiteralPath $ActiveOverlay -PathType Leaf) {
        Copy-Item -LiteralPath $ActiveOverlay -Destination $Baseline
    }
    elseif (Test-Path -LiteralPath (Join-Path $PanelDir "R36H.DTBO") -PathType Leaf) {
        Copy-Item -LiteralPath (Join-Path $PanelDir "R36H.DTBO") -Destination $Baseline
    }
    else {
        Fail "Nao existe overlay ativo nem R36H.DTBO. Prepare o overlay original antes de instalar o seletor."
    }
}

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
