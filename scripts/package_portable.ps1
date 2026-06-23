param(
    [string]$Version = "",
    [string]$OutputDir = "",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

function Get-GitPath {
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if ($gitCommand) {
        return $gitCommand.Source
    }

    $fallback = "C:\Program Files\Git\cmd\git.exe"
    if (Test-Path -LiteralPath $fallback) {
        return $fallback
    }

    throw "Git was not found. Install Git or add git.exe to PATH."
}

function Get-PyInstallerPath {
    $localPath = Join-Path $repoRoot ".venv\Scripts\pyinstaller.exe"
    if (Test-Path -LiteralPath $localPath) {
        return $localPath
    }

    $command = Get-Command pyinstaller -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "PyInstaller was not found. Install dependencies first, or create .venv with PyInstaller."
}

function Assert-InRepo {
    param([string]$Path)

    $rootWithSlash = [System.IO.Path]::GetFullPath($repoRoot + [System.IO.Path]::DirectorySeparatorChar)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is outside the repository: $fullPath"
    }
}

function Remove-InRepo {
    param(
        [string]$Path,
        [switch]$Recurse
    )

    Assert-InRepo -Path $Path
    if (Test-Path -LiteralPath $Path) {
        if ($Recurse) {
            Remove-Item -LiteralPath $Path -Recurse -Force
        } else {
            Remove-Item -LiteralPath $Path -Force
        }
    }
}

Push-Location $repoRoot
try {
    $git = Get-GitPath

    if ([string]::IsNullOrWhiteSpace($Version)) {
        $versionPath = Join-Path $repoRoot "VERSION"
        if (-not (Test-Path -LiteralPath $versionPath)) {
            throw "VERSION file was not found."
        }
        $Version = (Get-Content -LiteralPath $versionPath -Encoding UTF8 -Raw).Trim()
    }

    if ([string]::IsNullOrWhiteSpace($Version)) {
        throw "Version is empty."
    }

    $status = & $git status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "Git status check failed."
    }
    if ($status) {
        throw "Working tree has uncommitted changes. Commit or restore changes before packaging."
    }

    if ([string]::IsNullOrWhiteSpace($OutputDir)) {
        $OutputDir = Join-Path $repoRoot "dist"
    } elseif (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
        $OutputDir = Join-Path $repoRoot $OutputDir
    }
    Assert-InRepo -Path $OutputDir
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

    $safeVersion = $Version -replace '[\\/:*?"<>|]', "_"
    $packageBase = "TexCat_$safeVersion"
    $pyinstallerDist = Join-Path $OutputDir "pyinstaller"
    $pyinstallerBuild = Join-Path $repoRoot "build\pyinstaller"
    $pyinstallerApp = Join-Path $pyinstallerDist "TexCat"
    $portableDir = Join-Path $OutputDir "$packageBase`_portable"
    $zipPath = Join-Path $OutputDir "$packageBase`_portable.zip"
    $hashPath = "$zipPath.sha256"

    foreach ($path in @($pyinstallerDist, $pyinstallerBuild, $portableDir, $zipPath, $hashPath)) {
        Assert-InRepo -Path $path
    }

    if (-not $SkipBuild) {
        $pyinstaller = Get-PyInstallerPath
        & $pyinstaller --noconfirm --clean --onedir --windowed --name TexCat --icon assets\TexCat.ico --paths src --distpath $pyinstallerDist --workpath $pyinstallerBuild src\texture_toolbox.py
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller build failed."
        }
    }

    if (-not (Test-Path -LiteralPath $pyinstallerApp)) {
        throw "PyInstaller app folder was not found: $pyinstallerApp"
    }

    Remove-InRepo -Path $portableDir -Recurse
    Remove-InRepo -Path $zipPath
    Remove-InRepo -Path $hashPath

    New-Item -ItemType Directory -Path $portableDir | Out-Null
    Get-ChildItem -LiteralPath $pyinstallerApp -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $portableDir -Recurse -Force
    }

    Copy-Item -LiteralPath "assets" -Destination (Join-Path $portableDir "assets") -Recurse -Force
    Copy-Item -LiteralPath "docs" -Destination (Join-Path $portableDir "docs") -Recurse -Force
    New-Item -ItemType Directory -Force -Path (Join-Path $portableDir "output") | Out-Null

    Copy-Item -LiteralPath "PORTABLE_README.md" -Destination (Join-Path $portableDir "README.md") -Force
    Copy-Item -LiteralPath "LICENSE","VERSION" -Destination $portableDir -Force

    Compress-Archive -Path $portableDir -DestinationPath $zipPath -CompressionLevel Optimal

    $hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
    $hashLine = "$($hash.Hash)  $(Split-Path -Leaf $zipPath)"
    Set-Content -LiteralPath $hashPath -Encoding ASCII -Value $hashLine

    $file = Get-Item -LiteralPath $zipPath
    Write-Host ""
    Write-Host "Portable package created: $($file.FullName)"
    Write-Host "Size: $($file.Length) bytes"
    Write-Host "SHA256: $($hash.Hash)"
    Write-Host "Hash file: $hashPath"
    Write-Host ""
}
finally {
    Pop-Location
}
