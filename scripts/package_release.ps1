param(
    [string]$Version = "",
    [string]$OutputDir = ""
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

function Assert-InRepo {
    param([string]$Path)

    $rootWithSlash = [System.IO.Path]::GetFullPath($repoRoot + [System.IO.Path]::DirectorySeparatorChar)
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $fullPath.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Output path is outside the repository: $fullPath"
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
    $zipPath = Join-Path $OutputDir "$packageBase`_source.zip"
    $hashPath = "$zipPath.sha256"

    Assert-InRepo -Path $zipPath
    Assert-InRepo -Path $hashPath

    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    if (Test-Path -LiteralPath $hashPath) {
        Remove-Item -LiteralPath $hashPath -Force
    }

    $prefix = "$packageBase/"
    & $git archive --format=zip --output=$zipPath --prefix=$prefix HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "Source zip generation failed."
    }

    $hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256
    $hashLine = "$($hash.Hash)  $(Split-Path -Leaf $zipPath)"
    Set-Content -LiteralPath $hashPath -Encoding ASCII -Value $hashLine

    $file = Get-Item -LiteralPath $zipPath
    Write-Host ""
    Write-Host "Package created: $($file.FullName)"
    Write-Host "Size: $($file.Length) bytes"
    Write-Host "SHA256: $($hash.Hash)"
    Write-Host "Hash file: $hashPath"
    Write-Host ""
}
finally {
    Pop-Location
}
