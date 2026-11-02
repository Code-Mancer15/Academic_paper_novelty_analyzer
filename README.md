# Academic Paper Novelty Analyser (Novely)

A local-first research exploration tool for preliminary literature review. Upload a text-based PDF or enter paper metadata, maintain a reference library, and compare candidate contributions against it. The indicator is **not** a plagiarism verdict, an originality guarantee, or a validated scientific measurement. It cannot replace reading primary sources and searching the wider literature.

## What works

- React dashboard, upload/manual entry, metadata correction, searchable library, history and detailed reports.
- FastAPI, SQLAlchemy and SQLite persistence; background analysis and status polling. Historical reports are snapshots and survive paper deletion.
- PDF validation (10 MB, 300 pages, PDF signature, text extraction), section detection and heuristic contribution excerpts.
- Local literature provider; ranking and per-contribution comparisons, source excerpts, limitations, and printable HTML report (browser **Print → Save as PDF**).
- Empty-library safeguards: no combined score without query text, candidate contributions, and comparable references. Coverage and evidence strength are explicitly unscored because the library is not comprehensive.
- Optional local Sentence Transformers embeddings. Default TF-IDF fallback runs offline and is **lexical, not semantic**. The actual method is shown in each report.
- Demo library button inserts two prominently marked **fictional synthetic examples**, not academic citations. Remove them before a real review.

## Architecture

Vite/React/TypeScript, React Router, Recharts and Lucide communicate through the Vite `/api` proxy with FastAPI. SQLAlchemy stores papers, extracted section JSON and complete analysis snapshots in SQLite. PyMuPDF extracts text; regex heuristics select candidate sentences; scikit-learn computes cosine similarity over TF-IDF or Sentence Transformers vectors. The local literature provider is isolated in `backend/app/analysis.py`. CORS defaults to the local Vite origin. Interactive API docs: http://localhost:8000/docs.

The UI uses custom CSS components rather than Tailwind/shadcn; this is an implementation simplification. Extracted sections and results are stored as JSON fields instead of separate contribution/match tables. Embeddings are computed for each analysis, not persisted or cached; historical results do not rerun. There is no LLM, external academic metadata provider, or OCR integration. No API key is required or used. These are possible future enhancements.

## Windows setup

Prerequisites: Python 3.10–3.12 recommended (3.13 supported by the tested offline stack), Node.js 20+, npm and PowerShell. From the project root, in **terminal 1**:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If PowerShell prevents venv activation, run `Set-ExecutionPolicy -Scope Process Bypass` first, or invoke `.\.venv\Scripts\python.exe` directly. The SQLite database `backend/novelty.db` and tables are created automatically on startup. Do not delete this file if you want to preserve your history.

In **terminal 2**, from the project root:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Run tests and build in separate terminals:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

```powershell
cd frontend
npm run build
```

The test database is `backend/test_novelty.db`; tests reset its tables. Never set `DATABASE_URL` to a valuable database when running tests.

### Optional semantic model

For semantic comparison, install the optional dependencies in the backend environment and set environment variables **in the same backend terminal before starting Uvicorn**:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-semantic.txt
$env:EMBEDDING_BACKEND = "sentence-transformers"
$env:EMBEDDING_MODEL = "all-MiniLM-L6-v2"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The first analysis lazily downloads the model, requiring internet and disk space; subsequent runs use the model cache. If loading fails, analysis falls back to offline TF-IDF and labels the method. Installing PyTorch can be large; use a supported Python/PyTorch combination. No uploaded document is intentionally sent to a third-party API. Model download contacts the model hosting service. No LLM API is implemented.

`.env.example` lists supported variables; it is a reference, **not automatically loaded**. Set `DATABASE_URL`, `FRONTEND_ORIGIN`, `EMBEDDING_BACKEND`, and `EMBEDDING_MODEL` in the process environment as needed. The SQLite URL is relative to the backend working directory. Never commit secrets or real paper databases.

## Example usage

1. Go to Literature library and add real reference abstracts manually or upload their PDFs. Metadata and source information must be checked against the actual publication. Alternatively, select **Load demo papers** for two clearly fictional examples.
2. Choose Analyse paper, upload a text-based PDF or enter an abstract, review/correct metadata and start the analysis. Scanned PDFs require external OCR before upload.
3. Wait for the status to finish. Examine contribution and reference excerpts, similarity, limitations, and next steps. Use Print / save PDF to export.
4. Search/filter the library, revisit/delete reports in History. Adding references later does not change old reports; run a new analysis.

## Indicator and limits

Highest reference similarity is the maximum cosine similarity for the paper abstract (or fallback text) against usable library abstracts/text. Contribution distinctiveness is 100 minus the mean of each candidate contribution's highest reference similarity. When all required evidence exists, overall = 0.5 × (100 − highest similarity) + 0.5 × distinctiveness. Values are clipped to 0–100 and are unvalidated heuristics. Low similarity does not prove novelty; high similarity can reflect legitimate extensions or shared vocabulary. Evidence strength and coverage are intentionally “Insufficient evidence”, not invented scores. A small, biased or irrelevant library will produce misleading indicators; even a zero-similarity match is merely the closest available reference, not proof of relevance.

PDF extraction/metadata, section recognition and contribution detection are imperfect. Titles/authors are guessed from PDF metadata or the first line; edit them. No OCR, embedding cache, worker queue, authentication, source verification, external provider, LLM, or recovery for jobs interrupted by a server restart is included. This development app is intended for a trusted local user, not public deployment. A larger deployment needs authentication, persistent workers, security hardening, database migrations and privacy controls. The development frontend fetches Google Fonts when available; fallbacks work offline.

## Project map

- `backend/app/main.py` — API, job status, demo data, printable report.
- `backend/app/database.py` — SQLite models and sessions.
- `backend/app/processing.py` — PDF extraction and heuristic sections/contributions.
- `backend/app/analysis.py` — local provider, similarity and indicator calculation.
- `backend/tests/` — API, processing, error, persistence and report tests.
- `frontend/src/` — routes, API integration, components and responsive styling.
- `.env.example` — environment variable reference.
