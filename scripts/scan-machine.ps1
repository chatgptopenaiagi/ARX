param([string]$Output=(Join-Path (Get-Location) 'machine-dna.json'))
$ProjectRoot=Split-Path -Parent $PSScriptRoot;$env:PYTHONPATH=Join-Path $ProjectRoot 'src';python -m arx --output $Output deep
