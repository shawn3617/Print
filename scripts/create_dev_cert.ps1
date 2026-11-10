<#
.SYNOPSIS
    Генерация локального самоподписанного сертификата Code Signing для разработки и тестирования.
.DESCRIPTION
    Создает самоподписанный сертификат для цифровой подписи кода (Authenticode),
    помещает его в личное хранилище текущего пользователя (Cert:\CurrentUser\My)
    и экспортирует в файл dist\dev_cert.pfx с паролем по умолчанию 'PrintPDFDev'.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\create_dev_cert.ps1
#>

[CmdletBinding()]
param(
    [string]$CertSubject = "CN=PrintPDF Developer Test Certificate",
    [string]$CertPassword = "PrintPDFDev",
    [string]$PfxPath = "dist\dev_cert.pfx",
    [int]$ValidYears = 5
)

$ErrorActionPreference = "Stop"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Генерация тестового сертификата Code Signing (Authenticode)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Преобразуем относительный путь к PFX в абсолютный от корня проекта
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
if (-not [System.IO.Path]::IsPathRooted($PfxPath)) {
    $TargetPfx = Join-Path $ProjectRoot $PfxPath
} else {
    $TargetPfx = $PfxPath
}

$PfxDir = Split-Path -Parent $TargetPfx
if (-not (Test-Path $PfxDir)) {
    Write-Host "[ИНФО] Создание каталога: $PfxDir" -ForegroundColor Gray
    New-Item -ItemType Directory -Path $PfxDir -Force | Out-Null
}

Write-Host "Создание сертификата: $CertSubject..." -ForegroundColor Yellow
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject $CertSubject `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyUsage DigitalSignature `
    -KeySpec Signature `
    -NotAfter (Get-Date).AddYears($ValidYears)

Write-Host "Экспорт в PFX: $TargetPfx..." -ForegroundColor Yellow
$securePassword = ConvertTo-SecureString -String $CertPassword -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $TargetPfx -Password $securePassword | Out-Null

Write-Host ""
Write-Host "[УСПЕХ] Тестовый сертификат успешно сгенерирован и экспортирован!" -ForegroundColor Green
Write-Host "  Субъект:    $($cert.Subject)"
Write-Host "  Отпечаток:  $($cert.Thumbprint)"
Write-Host "  Действителен до: $($cert.NotAfter.ToString('yyyy-MM-dd'))"
Write-Host "  Файл PFX:   $TargetPfx"
Write-Host "  Пароль:     $CertPassword"
Write-Host ""
Write-Host "Теперь скрипт scripts\sign_binary.py автоматически найдет этот сертификат." -ForegroundColor Cyan
Write-Host "Для настройки в CI/CD используйте переменные окружения:" -ForegroundColor Gray
Write-Host "  SIGN_CERT_FILE=$TargetPfx" -ForegroundColor Gray
Write-Host "  SIGN_CERT_PASSWORD=$CertPassword" -ForegroundColor Gray
Write-Host "========================================================" -ForegroundColor Cyan
