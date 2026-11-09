# Simple Private RAG

Ask questions about your TXT files using AI models running on your computer.
The app shows source excerpts so you can check each answer.

Built with Python, FastAPI, SQLite, plain HTML/CSS/JavaScript, and Ollama.
No paid AI API key is required.

## Start on Windows

### 1. Install Python and Ollama

- Install [Python 3.12](https://www.python.org/downloads/windows/) with pip and the Python launcher.
- Install [Ollama for Windows](https://ollama.com/download/windows) and open it.
- Open a new PowerShell window and check both commands:

```powershell
py -3.12 --version
ollama --version
```

Allow several gigabytes for Ollama, model downloads, and Python packages.
Download time and answer speed depend on your computer and connection.

### 2. Keep Ollama local

To disable Ollama cloud features, run:

```powershell
[Environment]::SetEnvironmentVariable('OLLAMA_NO_CLOUD', '1', 'User')
```

Fully quit Ollama from the system tray, then reopen it so the setting takes effect.
See [Ollama's FAQ](https://docs.ollama.com/faq) for details.

### 3. Download this project

On GitHub, choose **Code > Download ZIP** and extract the folder.

Or, if Git is installed:

```powershell
git clone https://github.com/contactkvijay/SimplePrivateRag.git
cd SimplePrivateRag
```

### 4. Start the app

Double-click **Start-Local.cmd** in the extracted project folder.

The launcher creates a Python environment, installs packages, downloads
`embeddinggemma` and `qwen3.5:2b`, and warms the models.
Keep this terminal open while using the app.

When asked, choose a password. The characters are hidden while you type.
If startup fails, read the error left in the terminal.

### 5. Open the page

Open **http://127.0.0.1:8789/** in your browser.

- Username: `rag`
- Password: the password you just chose. There is no default password.

Wait for **Models ready**. If you already set `RAG_PASSWORD` in the launcher's
environment, it uses that value instead of asking for a password.

### 6. Upload and ask

Click **Upload TXT file** and select **sample.txt** from this project.
All its records are fictional.

Try:

- What is Ravi Example's Demo Maple Bank branch address?
- What database port does Demo Billing Portal use in Development?
- Who owns Demo Billing Portal?

Click **Ask**, or press Enter. Open **View source excerpts** to check the answer.
Use complete questions; previous chat turns are not sent with the next request.

To stop the app, press **Ctrl+C** in its terminal.

## Format your own notes

Use non-empty UTF-8 `.txt` files up to 8 MB. PDF, Word, and image uploads are not supported.
Keep related details together, repeat the person or project name, and separate
records with a line containing only three hyphens:

```text
Name: Ravi Example
Bank: Demo Maple Bank
Branch address: 10 Example Road, Demo City
---
Project: Demo Billing Portal
Environment: Development
Database port: 1540
```

Blank lines alone do not separate records. The app targets passages of about
700 characters; long records can split and a single long line can exceed that target.

- Upload the exact same filename again to replace its saved version.
- **Delete** removes a document, its passages, vectors, and saved TXT copy.
- **Clear chat** clears the conversation; uploaded documents remain.

## Files

```text
backend/
  app.py          Login and web routes
  ingestion.py    Read TXT and prepare passages
  retrieval.py    Call Ollama and assemble answers
  storage.py      Save, rank, replace and delete records
frontend/
  index.html      Page structure
  style.css       Page appearance
  app.js          Upload, question and document controls
tests/
  synthetic.txt   Fictional evaluation records
  test_hybrid.py  Ranking tests without Ollama
  evaluate.py     Retrieval and model evaluation
Start-Local.cmd    Windows entry point
Start-Local.ps1    Setup and server launcher
requirements.txt  Python packages
sample.txt        Fictional example for your first upload
```

## How it works

Upload: TXT -> passages -> embeddings -> SQLite.

Question: embed question -> rank passages -> send up to five to the local model -> answer with sources.

Search combines 65% cosine similarity with 35% keyword overlap. It scans
stored compatible vectors using NumPy. Uploading a file does not train the model.

## Privacy and limitations

- The downloaded models process document contents locally. Initial setup and
  the launcher's package/model checks use the internet.
- The server listens on loopback. This is a personal, single-user app; do not expose it publicly.
- The launcher stores uploads and SQLite data in `local-data/`. They are **not encrypted**.
  Login does not protect files from someone who can read your disk.
- `.gitignore` excludes local data, databases, credentials, and uploaded TXT files.
  It cannot remove files already committed; review changes before publishing.
- Answers and citations can be wrong. Check source names and exact values.
- Ordinary deletion does not securely erase disk contents or external backups.
- Changing the embedding model requires re-uploading documents.

## Optional tests

From PowerShell in the project folder, after first startup:

```powershell
.\.venv\Scripts\python.exe tests/test_hybrid.py
```

For 20 model-backed questions, keep Ollama running and use:

```powershell
.\.venv\Scripts\python.exe tests/evaluate.py
```

These tests use isolated fictional data. Evaluation writes
`.artifacts/hybrid-evaluation.json`; inspect failed cases. Exact-wording checks
can fail on model paraphrases, and this small evaluation does not prove general accuracy.

## License

[MIT](LICENSE)
