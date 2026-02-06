$ErrorActionPreference = "Stop"
$logFile = "publish_error.log"
$distDir = "dist"
$buildDir = "build"
$eggInfo = "txa_m.egg-info"
$requiredFiles = @("setup.py", "README.md", "txa_mediafire")

function Write-Log {
    param([string]$message)
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $message" | Out-File $logFile -Append -Encoding UTF8
}

Clear-Host
Write-Host "=== TXA-M Package Publisher ===" -ForegroundColor Cyan

# 1. Check requirements
Write-Host "[1/4] Checking file integrity..." -ForegroundColor Yellow
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        $msg = "CRITICAL: Missing required file or folder: '$file'. Cannot proceed."
        Write-Host $msg -ForegroundColor Red
        Write-Log $msg
        exit 1
    }
}

# 2. Cleanup old artifacts
Write-Host "[2/4] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path $eggInfo) { Remove-Item $eggInfo -Recurse -Force -ErrorAction SilentlyContinue }
if (Test-Path $logFile) { Remove-Item $logFile -Force -ErrorAction SilentlyContinue }

try {
    # 3. Build Package
    Write-Host "[3/4] Building package..." -ForegroundColor Cyan
    & python -m build
    if ($LASTEXITCODE -ne 0) { throw "Build command failed with exit code $LASTEXITCODE" }

    # 4. Upload to PyPI
    Write-Host "[4/4] Uploading to PyPI..." -ForegroundColor Cyan
    
    # Check if .pypirc exists or if we should warn
    if (-not (Test-Path "$env:USERPROFILE\.pypirc")) {
        Write-Host "WARNING: No .pypirc file found. You will be prompted for credentials." -ForegroundColor Magenta
        Write-Host "Enter '__token__' for username and your API Token for password." -ForegroundColor Magenta
    }

    & twine upload dist/*
    if ($LASTEXITCODE -ne 0) { throw "Twine upload failed with exit code $LASTEXITCODE" }

    Write-Host "`nSUCCESS: Package 'txa-m' has been successfully published!" -ForegroundColor Green
}
catch {
    $err = $_.Exception.Message
    Write-Host "`nFAILURE: The process failed." -ForegroundColor Red
    Write-Host "Reason: $err" -ForegroundColor Red
    Write-Log "Process Failed: $err"
    Write-Host "Check '$logFile' for details." -ForegroundColor Gray
}
finally {
    # 5. Final Cleanup
    Write-Host "`nCleaning up intermediate files (keeping 'dist')..." -ForegroundColor DarkGray
    if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force -ErrorAction SilentlyContinue }
    if (Test-Path $eggInfo) { Remove-Item $eggInfo -Recurse -Force -ErrorAction SilentlyContinue }
    Write-Host "Done." -ForegroundColor Cyan
}
