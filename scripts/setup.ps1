$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
if (-not (Test-Path '.venv/Scripts/python.exe')) { python -m venv .venv }
& '.venv/Scripts/python.exe' -m pip install -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
if (-not (Test-Path 'backend/.env')) {
    $randomBytes = New-Object byte[] 48
    $randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $randomGenerator.GetBytes($randomBytes)
    $randomGenerator.Dispose()
    $jwtValue = [Convert]::ToBase64String($randomBytes)
    $envText = Get-Content 'backend/.env.example' -Raw
    [IO.File]::WriteAllText((Join-Path $projectRoot 'backend/.env'), $envText.Replace('replace-with-a-random-secret-at-least-32-characters', $jwtValue), (New-Object System.Text.UTF8Encoding $false))
}
& '.venv/Scripts/python.exe' scripts/generate_sample.py
Push-Location frontend
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
Write-Host 'Dependencies installed. Configure backend/.env with your MySQL credentials, then follow README.md.'
