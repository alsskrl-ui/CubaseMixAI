$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
py -3.11 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required: install it first.' }
& .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Run .\.venv\Scripts\cubasemixai.exe ui in a separate terminal.'
Write-Host 'Install loopMIDI manually; create the CubaseMixAI port. Follow docs/windows-cubase.md.'
