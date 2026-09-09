$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$arguments = '-m celery -A config worker --pool=solo --loglevel=INFO --hostname=shop-worker@%h --logfile=celery-worker.log'
Start-Process -FilePath $python -WorkingDirectory $root -WindowStyle Hidden -ArgumentList $arguments
