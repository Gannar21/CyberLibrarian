<#
.SYNOPSIS
    Clean-clone integration test for CyberLibrarian.

.DESCRIPTION
    Clones the repo into a temp directory, creates a fresh venv, installs
    requirements, runs the corpus download, builds the sample index,
    runs pytest, runs a retrieve() call, runs an answer() call, and boots
    Streamlit headless.

    Prints PASS / FAIL / SKIPPED for each step, then a summary line.
    Never prints the LLM_API_KEY value.

.PARAMETER RepoRoot
    Path to the local repo to clone from.  Defaults to the parent of this
    script's directory (i.e. the repo root).

.PARAMETER KeepTemp
    If set, the temp clone is NOT deleted after the test so you can inspect it.

.EXAMPLE
    # Run from anywhere:
    powershell -File scripts/check_clean_clone.ps1

    # Keep the temp folder for inspection:
    powershell -File scripts/check_clean_clone.ps1 -KeepTemp
#>
param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [switch]$KeepTemp
)

$ErrorActionPreference = "Stop"
$results = [ordered]@{}

function Step-Run {
    param([string]$Name, [scriptblock]$Body, [string]$SkipReason = "")

    if ($SkipReason) {
        Write-Host "  SKIPPED  $Name  ($SkipReason)"
        $results[$Name] = "SKIPPED"
        return $true
    }

    Write-Host "  RUNNING  $Name ..."
    try {
        & $Body
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "exit $LASTEXITCODE" }
        Write-Host "  PASS     $Name"
        $results[$Name] = "PASS"
        return $true
    } catch {
        Write-Host "  FAIL     $Name  ($_)"
        $results[$Name] = "FAIL"
        return $false
    }
}

# ---------------------------------------------------------------------------
Write-Host "`nCyberLibrarian clean-clone test`n"

# Step 0: find git
$gitAvail = (Get-Command git -ErrorAction SilentlyContinue) -ne $null
if (-not $gitAvail) {
    Write-Host "FATAL: git not found in PATH"; exit 1
}

# Create temp directory
$TempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("cyberlib_test_" + [System.Guid]::NewGuid().ToString("N")[0..7] -join "")
New-Item -ItemType Directory -Path $TempDir | Out-Null
Write-Host "Temp directory: $TempDir`n"
$CloneDir = Join-Path $TempDir "repo"

try {
    # ── 1. Clone ─────────────────────────────────────────────────────────────
    Step-Run "clone" {
        git clone --quiet "$RepoRoot" "$CloneDir"
        Set-Location $CloneDir
    } | Out-Null

    if (-not (Test-Path $CloneDir)) {
        Write-Host "FATAL: clone failed; aborting"; exit 1
    }
    Set-Location $CloneDir

    # ── 2. Create venv ────────────────────────────────────────────────────────
    Step-Run "create-venv" {
        python -m venv .venv
    } | Out-Null

    $Python  = Join-Path $CloneDir ".venv\Scripts\python.exe"
    $Pip     = Join-Path $CloneDir ".venv\Scripts\pip.exe"

    # ── 3. Install requirements ───────────────────────────────────────────────
    Step-Run "pip-install" {
        & $Pip install --quiet -r requirements.txt
    } | Out-Null

    # ── 4. Download corpus ────────────────────────────────────────────────────
    Step-Run "download-corpus" {
        & $Python -m src.ingest.run
    } | Out-Null

    # ── 5. Build sample index ─────────────────────────────────────────────────
    Step-Run "build-index" {
        & $Python -m src.indexing.build_index --sample
    } | Out-Null

    # ── 6. Run pytest ─────────────────────────────────────────────────────────
    Step-Run "pytest" {
        & $Python -m pytest tests/ -q --tb=short
    } | Out-Null

    # ── 7. Retrieve ───────────────────────────────────────────────────────────
    # No API key required for retrieval; skip if index was not built.
    $indexBuilt = (Test-Path (Join-Path $CloneDir "indexes\bm25.pkl"))
    $skipRetrieve = if ($indexBuilt) { "" } else { "index not built (step 5 failed)" }

    Step-Run "retrieve" {
        & $Python -c @"
import sys; sys.path.insert(0, '.')
from src.retrieval.retriever import retrieve
results = retrieve('What is SQL injection?', k=3)
assert len(results) > 0, 'retrieve() returned empty list'
print(f'  retrieve() returned {len(results)} result(s)')
"@
    } -SkipReason $skipRetrieve | Out-Null

    # ── 8. Answer (needs LLM_API_KEY) ────────────────────────────────────────
    $hasKey = ($env:LLM_API_KEY -and $env:LLM_API_KEY.Length -gt 0) -or
              ($env:OPENAI_API_KEY -and $env:OPENAI_API_KEY.Length -gt 0)
    $skipAnswer = if ($hasKey) { "" } else { "LLM_API_KEY not set" }

    Step-Run "answer" {
        & $Python -c @"
import sys, os; sys.path.insert(0, '.')
os.environ['FAKE_LLM'] = '1'
from src.generation.answer import answer
resp = answer('What is SQL injection?')
assert resp.answer, 'answer() returned empty string'
print(f'  answer() returned {len(resp.answer)} chars')
"@
    } -SkipReason $skipAnswer | Out-Null

    # ── 9. Streamlit headless boot ────────────────────────────────────────────
    # Start streamlit, wait 10 s, check it is still alive, then kill it.
    Step-Run "streamlit-boot" {
        $env:USE_MOCK = "true"
        $proc = Start-Process -FilePath $Python `
            -ArgumentList "-m", "streamlit", "run", "app/streamlit_app.py",
                          "--server.headless", "true",
                          "--server.port", "8502",
                          "--browser.gatherUsageStats", "false" `
            -PassThru -WindowStyle Hidden
        Start-Sleep -Seconds 12
        if ($proc.HasExited) {
            throw "Streamlit exited early (exit $($proc.ExitCode))"
        }
        Stop-Process -Id $proc.Id -Force
    } | Out-Null

} finally {
    # ── Summary ───────────────────────────────────────────────────────────────
    Set-Location $RepoRoot
    Write-Host "`n----"
    $pass = 0; $fail = 0; $skip = 0
    foreach ($kv in $results.GetEnumerator()) {
        $icon = switch ($kv.Value) { "PASS" { "[+]" } "FAIL" { "[!]" } default { "[-]" } }
        Write-Host "  $icon $($kv.Key): $($kv.Value)"
        if ($kv.Value -eq "PASS")    { $pass++ }
        elseif ($kv.Value -eq "FAIL") { $fail++ }
        else                          { $skip++ }
    }
    Write-Host "`n  Summary: $pass PASS  $fail FAIL  $skip SKIPPED"

    if (-not $KeepTemp) {
        Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
    } else {
        Write-Host "  Temp dir kept: $TempDir"
    }

    if ($fail -gt 0) { exit 1 } else { exit 0 }
}
