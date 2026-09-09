# Verifie les prerequis et prepare les modeles Ollama pour RAG Local.
# Usage : powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1

$ErrorActionPreference = "Stop"

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

Write-Host "== Verification des prerequis ==" -ForegroundColor Cyan

if (-not (Test-Command "ollama")) {
    Write-Host "Ollama n'est pas installe ou pas dans le PATH." -ForegroundColor Red
    Write-Host "Installe-le depuis https://ollama.com puis relance ce script."
    exit 1
}
Write-Host "OK - Ollama trouve"

if (-not (Test-Command "docker")) {
    Write-Host "Docker n'est pas installe ou pas dans le PATH." -ForegroundColor Yellow
    Write-Host "Docker Desktop est requis pour 'docker-compose up' (facultatif si tu lances backend/frontend manuellement)."
} else {
    Write-Host "OK - Docker trouve"
}

Write-Host "`n== Telechargement des modeles (si absents) ==" -ForegroundColor Cyan
$chatModel = "qwen3:8b"
$embedModel = "nomic-embed-text"
$visionModel = "qwen3-vl:4b"

$installed = ollama list

foreach ($model in @($chatModel, $embedModel, $visionModel)) {
    if ($installed -match [regex]::Escape($model)) {
        Write-Host "OK - $model deja present"
    } else {
        Write-Host "Telechargement de $model..."
        ollama pull $model
    }
}

Write-Host "`n== Pret ! ==" -ForegroundColor Green
Write-Host "1. Verifie qu'Ollama tourne (icone dans la barre des taches, ou 'ollama serve')."
Write-Host "2. Lance 'docker-compose up --build' depuis la racine du projet."
Write-Host "3. Ouvre http://localhost:3000"
Write-Host "`nPour un dev sans Docker : voir le README (section 'Dev local')."
