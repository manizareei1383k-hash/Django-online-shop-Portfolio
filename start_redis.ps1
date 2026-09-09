$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$server = Get-ChildItem -LiteralPath (Join-Path $root '.redis-server') -Recurse -Filter 'memurai.exe' | Select-Object -First 1
if (-not $server) {
    throw 'Memurai executable was not found. Install/download Redis first.'
}
if (-not (Get-NetTCPConnection -LocalPort 6379 -State Listen -ErrorAction SilentlyContinue)) {
    $service = Get-Service -Name 'DjangoShopRedis' -ErrorAction SilentlyContinue
    if ($service) {
        Start-Service -Name 'DjangoShopRedis'
        Start-Sleep -Milliseconds 500
        & (Join-Path $server.DirectoryName 'memurai-cli.exe') ping
        exit
    }
    $configuration = Join-Path $root 'redis.local.conf'
    Start-Process -FilePath $server.FullName -ArgumentList @("`"$configuration`"") `
        -WorkingDirectory $server.DirectoryName -WindowStyle Hidden
}
Start-Sleep -Milliseconds 500
& (Join-Path $server.DirectoryName 'memurai-cli.exe') ping
