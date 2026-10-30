[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$BootDrive
)

$ErrorActionPreference = 'Stop'
$ProfileName = 'mipi-panel.dtbo.r36s-panel4'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path`r`n$PackageRoot = if (Test-Path -LiteralPath (Join-Path $ScriptDir 'profiles\official\manifest.json')) { $ScriptDir } else { Split-Path -Parent $ScriptDir }
$ProfilePath = Join-Path $PackageRoot ('profiles\official\' + $ProfileName)
$CatalogPath = Join-Path $PackageRoot 'profiles\official\manifest.json'

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Test-ReparsePoint([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $item = Get-Item -LiteralPath $Path -Force
    return (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
}

try {
    $driveLetter = $BootDrive.Trim().TrimEnd('\').TrimEnd(':')
    if ($driveLetter -notmatch '^[A-Za-z]$') {
        throw 'Informe somente a letra da partição ROCKNIX, por exemplo E:'
    }

    $root = $driveLetter.ToUpperInvariant() + ':\'
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        throw ('Unidade não encontrada: ' + $root)
    }

    $volume = Get-Volume -DriveLetter $driveLetter -ErrorAction Stop
    $label = [string]$volume.FileSystemLabel
    $fileSystem = [string]$volume.FileSystem

    $bootMarkers = @('boot.ini', 'extlinux.conf', 'boot.scr', 'uEnv.txt', 'Image', 'uImage')
    $hasBootMarker = $false
    foreach ($marker in $bootMarkers) {
        if (Test-Path -LiteralPath (Join-Path $root $marker) -PathType Leaf) {
            $hasBootMarker = $true
            break
        }
    }
    $hasDtb = @(Get-ChildItem -LiteralPath $root -Filter '*.dtb' -File -ErrorAction SilentlyContinue).Count -gt 0
    if (($label -notmatch 'ROCKNIX|BOOT') -and (-not $hasBootMarker) -and (-not $hasDtb)) {
        throw ('A unidade ' + $root + ' não foi reconhecida como partição de boot. Rótulo=' +
            $label + '; sistema de arquivos=' + $fileSystem +
            '. Não foi feita nenhuma alteração. Selecione a partição ROCKNIX, não a partição de jogos.')
    }

    if (-not (Test-Path -LiteralPath $ProfilePath -PathType Leaf)) {
        throw ('DTBO Panel 4 ausente no pacote: ' + $ProfilePath)
    }
    if (-not (Test-Path -LiteralPath $CatalogPath -PathType Leaf)) {
        throw ('Manifesto de perfis ausente: ' + $CatalogPath)
    }

    $catalog = Get-Content -LiteralPath $CatalogPath -Raw | ConvertFrom-Json
    $entries = @($catalog.profiles | Where-Object { $_.file -eq $ProfileName })
    if ($entries.Count -ne 1) {
        throw 'O perfil Panel 4 não aparece exatamente uma vez no manifesto do pacote.'
    }

    $expectedHash = ([string]$entries[0].sha256).ToLowerInvariant()
    $expectedSize = [int64]$entries[0].size
    if ($expectedHash -notmatch '^[0-9a-f]{64}$') {
        throw 'SHA-256 inválido no manifesto do catálogo.'
    }
    $sourceHash = Get-Sha256 $ProfilePath
    $sourceSize = (Get-Item -LiteralPath $ProfilePath).Length
    if (($sourceHash -ne $expectedHash) -or ($sourceSize -ne $expectedSize)) {
        throw 'O DTBO do pacote não corresponde ao tamanho/SHA-256 do manifesto. Não será instalado.'
    }

    $overlayDir = Join-Path $root 'overlays'
    if (Test-ReparsePoint $overlayDir) {
        throw 'A pasta overlays é um link/reparse point. Operação bloqueada.'
    }
    if (Test-Path -LiteralPath $overlayDir -PathType Leaf) {
        throw 'Já existe um arquivo chamado overlays; não será substituído.'
    }

    $target = Join-Path $overlayDir 'mipi-panel.dtbo'
    if (Test-ReparsePoint $target) {
        throw 'O destino mipi-panel.dtbo é um link/reparse point. Operação bloqueada.'
    }
    if ((Test-Path -LiteralPath $target) -and (-not (Test-Path -LiteralPath $target -PathType Leaf))) {
        throw 'O destino mipi-panel.dtbo existe, mas não é um arquivo regular.'
    }

    Write-Host ''
    Write-Host 'IDENTIFYPANEL — PREPARAÇÃO ANTES DO PRIMEIRO BOOT' -ForegroundColor Cyan
    Write-Host ('Unidade: ' + $root)
    Write-Host ('Rótulo: ' + $label + ' | Sistema de arquivos: ' + $fileSystem)
    Write-Host ('Perfil: ' + $ProfileName)
    Write-Host ('Tamanho: ' + $sourceSize + ' bytes')
    Write-Host ('SHA-256: ' + $sourceHash)
    Write-Host ''
    Write-Host 'Este procedimento só altera overlays/mipi-panel.dtbo.'
    Write-Host 'Não altera boot.ini, extlinux.conf, boot.scr, DTB principal ou U-Boot.'
    Write-Host 'A identificação Panel 4 (V5) para R36H é comunitária; não é certificação oficial ROCKNIX.'
    Write-Host ''

    $confirmation = Read-Host ('Para preparar ' + $root + ' para a primeira inicialização, digite PREPARAR')
    if ($confirmation -cne 'PREPARAR') {
        Write-Host 'Cancelado. Nenhum arquivo foi alterado.'
        exit 0
    }

    if ($PSCmdlet.ShouldProcess($target, ('Instalar o perfil ' + $ProfileName))) {
        if (-not (Test-Path -LiteralPath $overlayDir -PathType Container)) {
            New-Item -ItemType Directory -Path $overlayDir | Out-Null
        }

        $backup = $null
        $temporary = Join-Path $overlayDir 'mipi-panel.dtbo.identifypanel-tmp'
        try {
            if (Test-Path -LiteralPath $target -PathType Leaf) {
                $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
                $backup = Join-Path $overlayDir ('mipi-panel.dtbo.pre-identifypanel-' + $stamp + '.bak')
                Copy-Item -LiteralPath $target -Destination $backup
                if ((Get-Sha256 $backup) -ne (Get-Sha256 $target)) {
                    throw 'Falha ao verificar o backup do overlay anterior. O original foi preservado.'
                }
                Write-Host ('Backup do overlay anterior: ' + $backup)
            }

            if (Test-Path -LiteralPath $temporary) {
                Remove-Item -LiteralPath $temporary -Force
            }
            Copy-Item -LiteralPath $ProfilePath -Destination $temporary
            if ((Get-Sha256 $temporary) -ne $expectedHash) {
                throw 'A cópia temporária falhou na verificação SHA-256.'
            }

            Move-Item -LiteralPath $temporary -Destination $target -Force
            if ((Get-Sha256 $target) -ne $expectedHash) {
                throw 'O arquivo gravado não passou na verificação SHA-256.'
            }

            $report = @(
                'IdentifyPanel - preparação pré-primeiro-boot',
                ('Data: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss K')),
                'Dispositivo-alvo: R36H (identificação comunitária de painel Panel 4 V5)',
                ('Perfil: ' + $ProfileName),
                ('Tamanho: ' + $sourceSize),
                ('SHA-256: ' + $expectedHash),
                ('Backup anterior: ' + $(if ($backup) { $backup } else { 'não existia overlay anterior' })),
                'Arquivo ativo: overlays\mipi-panel.dtbo',
                'Arquivos de boot e DTB principal: não modificados'
            )
            Set-Content -LiteralPath (Join-Path $root 'IDENTIFYPANEL-FIRST-BOOT.txt') -Value $report -Encoding ASCII

            Write-Host ''
            Write-Host 'PREPARAÇÃO CONCLUÍDA. O cartão está pronto para a primeira tentativa.' -ForegroundColor Green
            Write-Host ('Arquivo ativo: ' + $target)
            Write-Host ('SHA-256 confirmado: ' + (Get-Sha256 $target))
            Write-Host 'Use Remover com segurança/ejetar no Windows antes de retirar o cartão.'
        }
        catch {
            if ($backup -and (Test-Path -LiteralPath $backup -PathType Leaf)) {
                Copy-Item -LiteralPath $backup -Destination $target -Force
            } elseif (Test-Path -LiteralPath $target -PathType Leaf) {
                Remove-Item -LiteralPath $target -Force
            }
            throw
        }
        finally {
            if (Test-Path -LiteralPath $temporary) {
                Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
            }
        }
    }
}
catch {
    Write-Host ('ERRO: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
