<#
  Windows equivalent of the Makefile.  Usage:  .\tasks.ps1 <target>
  Targets: install, migrate, backend, frontend, dev, lint, format, test, test-all,
           e2e, perf, up, down, check-ground-truth, benchmark-dry, package
#>
param([Parameter(Position = 0)][string]$Target = "help")

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Py = Join-Path $Root "backend\.venv\Scripts\python.exe"

function In($dir, [scriptblock]$block) {
    Push-Location (Join-Path $Root $dir)
    try { & $block; if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE)" } }
    finally { Pop-Location }
}

switch ($Target) {
    "install" {
        In "backend" { python -m venv .venv; & $Py -m pip install -e ".[dev]" }
        In "backend\app\static_analysis\eslint" { npm install --omit=dev }
        In "frontend" { npm install }
    }
    "migrate" { In "backend" { & $Py -m alembic upgrade head } }
    "backend" { In "backend" { & $Py -m alembic upgrade head; & $Py -m uvicorn app.main:app --reload --port 8000 } }
    "frontend" { In "frontend" { npm run dev } }
    "dev" {
        In "backend" { & $Py -m alembic upgrade head }
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$Root\backend'; & '$Py' -m uvicorn app.main:app --reload --port 8000"
        In "frontend" { npm run dev }
    }
    "lint" {
        In "backend" { & $Py -m ruff check --config pyproject.toml app tests ..\evaluation\scripts }
        In "backend" { & $Py -m black --config pyproject.toml --check app tests ..\evaluation\scripts }
        In "frontend" { npm run lint }
    }
    "format" {
        In "backend" { & $Py -m ruff check --config pyproject.toml --fix app tests ..\evaluation\scripts }
        In "backend" { & $Py -m black --config pyproject.toml app tests ..\evaluation\scripts }
        In "frontend" { npm run format }
    }
    "test" {
        & $PSCommandPath lint
        In "backend" { & $Py -m pytest -m "not tools and not perf and not live_gemini" }
        In "frontend" { npm run test }
    }
    "test-all" {
        In "backend" { & $Py -m pytest -m "not perf and not live_gemini" }
        In "frontend" { npm run test }
    }
    "e2e" {
        In "." { docker compose up -d --build }
        In "frontend" { npx playwright test }
    }
    "perf" { In "backend" { & $Py -m pytest -m perf tests/perf -s } }
    "up" { In "." { docker compose up --build } }
    "down" { In "." { docker compose down } }
    "check-ground-truth" { In "." { & $Py evaluation\scripts\check_ground_truth.py } }
    "benchmark-dry" {
        $env:LLM_PROVIDER = "mock"
        In "." { & $Py evaluation\scripts\run_benchmark.py --conditions system baseline --runs 2 --out evaluation\results\dry-run }
        In "." { & $Py evaluation\scripts\score_benchmark.py --results evaluation\results\dry-run }
    }
    "package" {
        # Client zip: prebuilt frontend in backend\static; no .env, databases, virtual environments or node_modules.
        In "frontend" { npm run build }
        $Stage = Join-Path $env:TEMP "xai-package"
        $App = Join-Path $Stage "xai-code-review"
        if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
        robocopy $Root $App /E /NFL /NDL /NJH /NJS /NP `
            /XD node_modules .venv __pycache__ .pytest_cache .ruff_cache test-results playwright-report `
                data work tools dist "C%3A" xai_code_review.egg-info .git .vscode .idea `
            /XF .env *.db *.db-shm *.db-wal *.db-journal *.pyc .coverage | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
        robocopy (Join-Path $Root "frontend\dist") (Join-Path $App "backend\static") /E /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
        $global:LASTEXITCODE = 0
        $Zip = Join-Path (Split-Path $Root -Parent) "xai-code-review-client.zip"
        if (Test-Path $Zip) { Remove-Item -Force $Zip }
        & "$env:SystemRoot\System32\tar.exe" -a -c -f $Zip -C $Stage "xai-code-review"
        if ($LASTEXITCODE -ne 0) { throw "zip failed ($LASTEXITCODE)" }
        Remove-Item -Recurse -Force $Stage
        Write-Host "Created $Zip ($([math]::Round((Get-Item $Zip).Length / 1MB, 1)) MB)"
    }
    default { Get-Help $PSCommandPath; Write-Host "Targets: install migrate backend frontend dev lint format test test-all e2e perf up down check-ground-truth benchmark-dry package" }
}
