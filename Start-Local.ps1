$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Package installation failed.' }
ollama pull embeddinggemma
if ($LASTEXITCODE -ne 0) { throw 'Could not download the embedding model.' }
ollama pull qwen3.5:2b
if ($LASTEXITCODE -ne 0) { throw 'Could not download the answer model.' }
$env:RAG_CHAT_MODEL = 'qwen3.5:2b'
$env:RAG_DATA_DIR = Join-Path $PSScriptRoot 'local-data'
if (-not $env:RAG_PASSWORD) {
    $securePassword = Read-Host 'Choose a password (Chrome username is rag)' -AsSecureString
    $env:RAG_PASSWORD = [System.Net.NetworkCredential]::new('', $securePassword).Password
}
if (-not $env:RAG_PASSWORD) { throw 'A non-empty password is required.' }
Write-Host 'Warming up local models. The first startup can take a little longer...'
@'
from backend.retrieval import embedding, ollama, CHAT_MODEL
embedding('Warm up')
ollama('/api/chat', {'model': CHAT_MODEL, 'messages': [], 'stream': False,
                     'think': False, 'keep_alive': '30m', 'options': {'num_ctx': 2048}})
'@ | & $python -
if ($LASTEXITCODE -ne 0) { throw 'Model warm-up failed. Check that Ollama is running.' }
Write-Host 'Open http://127.0.0.1:8789/ in Chrome. Sign in as rag with your chosen password.'
& $python -m uvicorn backend.app:app --host 127.0.0.1 --port 8789
