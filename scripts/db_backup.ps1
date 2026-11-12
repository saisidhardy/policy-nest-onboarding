param(
    [string]$OutputDir = ".\backups",
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"
$PgUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "policynest" }
$PgDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "policynest" }
$ComposeFile = if ($env:COMPOSE_FILE) { $env:COMPOSE_FILE } else { "docker-compose.yml" }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$DumpPath = Join-Path $OutputDir "policynest_$Stamp.dump"

Write-Host "Creating compressed PostgreSQL backup at $DumpPath ..."
$cmd = "pg_dump -U $PgUser -d $PgDb --format=custom --no-owner --no-acl"
cmd /c "docker compose -f `"$ComposeFile`" exec -T db $cmd > `"$DumpPath`""
if ($LASTEXITCODE -ne 0) {
    throw "pg_dump failed with exit code $LASTEXITCODE"
}

$hash = (Get-FileHash -Path $DumpPath -Algorithm SHA256).Hash.ToLowerInvariant()
"$hash  $(Split-Path -Leaf $DumpPath)" | Out-File -Encoding ascii "$DumpPath.sha256"

Write-Host "Pruning backups older than $RetentionDays days..."
$cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $OutputDir -Filter "policynest_*.dump*" | Where-Object { $_.LastWriteTime -lt $cutoff } | Remove-Item -Force

Write-Host "Backup complete: $DumpPath (SHA-256: $hash)"
