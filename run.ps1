$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$env:PYTHONIOENCODING = "utf-8"
if (Test-Path ".\.venv\Lib\site-packages") {
    $env:PYTHONPATH = "$Root\.venv\Lib\site-packages"
}
& "python" -m app.main
