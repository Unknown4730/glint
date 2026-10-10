# GLINT — See beyond the page.

**GLINT** is a lightweight, *local* OCR and document digitization system.
Drop a scanned document, photo or PDF page on it and it returns clean, editable
text — recognized by a compact OCR model that runs **entirely on your CPU**.
No cloud service, no API key, no account, no GPU, no Docker.

> Simple on the surface. Reliable underneath.

```
┌───────────────────────────┐      /api (proxied)     ┌──────────────────────────┐
│  React 19 + Vite 7 UI     │ ──────────────────────► │  FastAPI (uvicorn, 1 w.) │
│  TypeScript, Tailwind 4   │                         │  sync routes + threadpool│
│  http://localhost:5173    │ ◄────────────────────── │  http://127.0.0.1:8000   │
└───────────────────────────┘        JSON only        └──────────┬───────────────┘
                                                                 │ one document at a time
                                    ┌────────────────────────────┼───────────────────────────┐
                                    ▼                            ▼                           ▼
                          ┌──────────────────┐        ┌───────────────────┐        ┌──────────────────┐
                          │ RapidOCR 3.10    │        │ SQLite (stdlib)   │        │ pandas +         │
                          │ ONNX Runtime CPU │        │ backend/data/     │        │ matplotlib chart │
                          │ PP-OCRv6 "small" │        │ glint.db          │        │ /api/analytics   │
                          └──────────────────┘        └───────────────────┘        └──────────────────┘
```

---

## 1. Requirements

| Component | Requirement | Notes |
|---|---|---|
| OS | Windows 10 / 11 | No WSL, no Docker |
| Python | **3.11** (3.12 / 3.13 also work) | 64-bit, on `PATH` |
| Node.js | ≥ 20.19 (22 LTS recommended) | Vite 7 requirement |
| CPU / RAM | i5-7300HQ / 8 GB is the reference machine | CPU inference only |
| GPU | none | CUDA is never used or required |
| Internet | first install only | packages are downloaded once; the OCR models ship **inside** the `rapidocr` wheel, so OCR then works offline |

## 2. Install (exact commands, Windows PowerShell)

From the project root, in PowerShell:

```powershell
.\install.ps1
```

That single script: checks Python and Node, creates `.venv`, installs
`backend\requirements.txt`, verifies that the local OCR engine really
initializes and reads a probe image, installs the frontend with npm, and
creates `.env` from `.env.example`. It stops with a clear message if any
required step fails.

Useful switches:

```powershell
.\install.ps1 -SkipFrontend          # Python side only
.\install.ps1 -SkipOcrCheck          # skip the OCR verification step
.\install.ps1 -PythonCommand "py"    # force a specific interpreter
```

## 3. Start (exact commands)

One command, two windows:

```powershell
.\start.ps1
```

`start.ps1` opens the backend and the frontend in two separate PowerShell
windows, waits until both really answer, prints the URLs and opens your
browser. It never starts a duplicate: if the API already answers on
`/api/health` (or the frontend already answers on its port) the existing
process is reused.

If you prefer to watch the logs yourself, use the two-terminal approach:

```powershell
# Terminal 1
.\run-backend.ps1

# Terminal 2
.\run-frontend.ps1
```

Optional switches: `.\start.ps1 -BackendOnly`, `.\start.ps1 -FrontendOnly`,
`.\start.ps1 -NoBrowser`. A production-style single-port run is also possible:
`npm run build` inside `frontend/`, then `.\run-backend.ps1` — the backend
serves `frontend/dist` at `/` when that folder exists.

### Local URLs

| What | URL |
|---|---|
| Glint UI (Vite dev server) | http://localhost:5173 |
| API | http://127.0.0.1:8000 |
| Interactive API docs (Swagger) | http://127.0.0.1:8000/api/docs |
| Health check | http://127.0.0.1:8000/api/health |

The browser only ever talks to `/api/...` on its own origin; the Vite dev
server proxies that path to `http://127.0.0.1:8000`, so there is no CORS
problem in development and no URL is hardcoded in the React code. To point
the UI at a different API, copy `frontend/.env.example` to `frontend/.env` and
set `VITE_API_BASE_URL=http://127.0.0.1:8000` (CORS then allows the two
localhost origins configured in `GLINT_CORS_ORIGINS`).

## 4. What Glint does

| Screen | What you get |
|---|---|
| **Workspace** | Drag-and-drop / file picker upload, client-side pre-validation, one **Extract Text** action, real processing state with an elapsed timer (no fake progress), then the recognized text with metadata cards (pages, duration, characters, engine), copy / download / reading-view actions and a "detected patterns" section. |
| **History** | Every finished job stored in SQLite: filename, type, pages, duration, character count, timestamp. Search by filename, open any result again, delete one entry, or clear everything behind a confirmation dialog. |
| **Analytics** | Real aggregates computed with pandas (documents, pages, average/fastest/slowest duration, most used file type, characters) plus one matplotlib PNG chart (activity of the last 14 days + file-type distribution). An empty database shows a proper empty state, never fabricated numbers. |
| **About Glint** | Architecture, limits, privacy notes, known limitations and a concept map for the viva. |

**Detected patterns** are plain regular expressions over the recognized text —
email addresses, date-like strings and currency amounts. They are hints, not
verified facts, and the UI says so.

## 5. Supported formats and limits

Configured in **one place**: `backend/app/config.py` (every value can be
overridden with a `GLINT_*` environment variable, see `.env.example`).

| Limit | Default | Variable |
|---|---|---|
| Maximum file size | **10 MB** | `GLINT_MAX_FILE_SIZE_MB` |
| Maximum PDF pages | **10** | `GLINT_MAX_PDF_PAGES` |
| Maximum image side | **3000 px** (aspect preserved) | `GLINT_MAX_IMAGE_SIDE_PX` |
| PDF render resolution | **150 DPI** | `GLINT_PDF_RENDER_DPI` |
| Accepted formats | `.pdf .png .jpg .jpeg .webp` | — |
| History page size | 50 rows | `GLINT_HISTORY_PAGE_SIZE` |

Validation is **content-based**: magic bytes decide the real type, Pillow
`verify()` catches truncated images, PyMuPDF catches broken PDFs, encrypted
PDFs are rejected instead of decrypted, and oversized uploads are refused
before expensive processing begins. A text file renamed to `.png` is rejected.

## 6. The OCR engine (and the model cache)

* Engine: **RapidOCR 3.10.0** with the **ONNX Runtime 1.23.2** CPU provider.
* Models: PP-OCRv6 **small** detection + recognition, plus the PP-OCRv4 mobile
  orientation classifier. All three are **bundled inside the `rapidocr` wheel**
  (about 31 MB) under `.../site-packages/rapidocr/models/`.
* Therefore: the first `pip install` needs internet, but **no model download
  ever happens for the default profile**, and OCR keeps working with the
  network switched off. `install.ps1` proves this by running
  `backend/scripts/verify_ocr.py`, which initializes the engine and reads a
  generated probe image.
* The engine is created **once** at start-up (plus a tiny warm-up inference so
  `/api/health` tells the truth and your first document is not slowed down by
  model loading) and then reused for every request behind a lock: exactly one
  document, and one PDF page, is processed at a time.
* `GLINT_OCR_MODEL_TYPE=tiny` / `medium` are genuinely supported RapidOCR model
  types but are **not** bundled; they are downloaded once on first use. The
  default stays `small` precisely because it needs no download.

Run the check any time:

```powershell
cd backend
..\.venv\Scripts\python scripts\verify_ocr.py
```

## 7. Run the tests

```powershell
# fast suite (94 tests): API, validation, database, analytics, regex — OCR mocked
cd backend
..\.venv\Scripts\python -m pytest

# plus the 4 real-OCR integration tests (~12 s, needs the bundled models)
..\.venv\Scripts\python -m pytest -m integration

# frontend type check + production build
cd ..\frontend
npm run build
```

Tests never download models: the fast suite swaps in a stub OCR service; the
integration tests are skipped automatically when RapidOCR or its model files
are missing.

## 8. Privacy and offline behaviour

* Documents never leave the machine: no cloud OCR, no telemetry, no paid API.
* An upload is written to a **temporary directory** that is deleted when the
  request ends — including when processing raises an exception. The original
  file is never stored anywhere.
* Only extracted text and metadata are persisted, in
  `backend/data/glint.db` (SQLite, created automatically on start-up).
  History can be deleted per entry or cleared completely from the UI.
* The backend binds to `127.0.0.1` by default; nothing is exposed publicly
  unless you explicitly set `GLINT_BACKEND_HOST` / `GLINT_FRONTEND_HOST`.
* First installation requires internet (packages). After that, OCR works
  offline — verified in this repository by running the whole pipeline with the
  bundled models and no model download.

## 9. Project structure

```
glint/
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI app, routes, error handlers, CORS
│   │   ├── config.py             every limit / path / tunable in one place
│   │   ├── database.py           SQLite (stdlib sqlite3, parameterized SQL)
│   │   ├── ocr_service.py        RapidOCR wrapper: init, warm-up, lock, status
│   │   ├── document_service.py   validation, image loading, PDF page loop
│   │   ├── text_utils.py         text clean-up + regex pattern extraction
│   │   ├── analytics_service.py  pandas summary + one matplotlib chart
│   │   └── schemas.py            pydantic response models
│   ├── scripts/verify_ocr.py     "does the local engine really work?" check
│   ├── tests/                    98 tests (94 mocked + 4 real OCR)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/           Button, Panel, Dropzone, ResultPanel, …
│   │   ├── pages/                Workspace / History / Analytics / About
│   │   ├── hooks/                useHealth, useToast, useClipboard
│   │   ├── services/api.ts       the one module that talks to the backend
│   │   ├── lib/format.ts         bytes / duration / date formatting
│   │   ├── types/index.ts        mirrors backend/app/schemas.py
│   │   ├── App.tsx, main.tsx, index.css (Tailwind v4 design tokens)
│   └── vite.config.ts            /api proxy, host/port/allowedHosts settings
├── scripts/glint-env.ps1         shared PowerShell helpers
├── .env.example                  backend + scripts configuration
├── .gitignore
├── install.ps1 / start.ps1 / run-backend.ps1 / run-frontend.ps1
└── README.md
```

## 10. Concept map (for the viva)

| Course concept | Where it lives |
|---|---|
| Functions, conditions, loops, dictionaries | every backend module, e.g. `text_utils.py` |
| Exception handling | `document_service.py` maps each failure to a status code and a short machine-readable code |
| File handling & safe temp files | `main.py::_process_upload` (temporary dir, always removed in `finally`) |
| Object-oriented programming | `OCRService` in `ocr_service.py` (init, warm-up, lock, status) |
| Regular expressions | `text_utils.py`: emails, dates, currency |
| Pandas | `analytics_service.py::compute_summary` |
| NumPy | `document_service.py::brightness_stats` (mean/std over a tiny thumbnail) |
| Matplotlib | `analytics_service.py::render_chart_png` (Agg backend, no GUI) |
| SQLite | `database.py` (schema auto-created, parameterized queries only) |
| PyMuPDF + Pillow | page rendering, image verification, EXIF, resizing |

## 11. Known limitations

* Optimized for ordinary **printed** text and document scans. Handwriting,
  dense tables, music notation and exotic layouts are out of scope; multi-column
  pages come back as reading-order lines, not as a reconstructed layout.
* One document at a time, pages sequential — deliberate, to stay inside 8 GB.
* Password-protected PDFs are rejected.
* Language coverage follows the bundled PP-OCRv6 model (Latin scripts plus
  Chinese). Other scripts need a different model.
* The analytics chart shows the last 14 days of activity; older history is
  still counted in the summary numbers.

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| `start.ps1` says the backend is not healthy | Look at the "GLINT backend" window. Usually a port clash (`GLINT_BACKEND_PORT` in `.env`) or a failed dependency. |
| UI shows "OCR unavailable" | Run `backend\scripts\verify_ocr.py`. If it fails, `pip install --force-reinstall rapidocr==3.10.0 onnxruntime==1.23.2`. |
| `pip install` fails with a wheel error | You are probably on Python < 3.11 or > 3.13. Use Python 3.11. |
| Vite refuses to answer on another host name | Set `GLINT_FRONTEND_ALLOWED_HOSTS` in `.env` (comma separated list, or `*`). |
| Port 5173 / 8000 already in use | Close the other Glint window, or change `GLINT_FRONTEND_PORT` / `GLINT_BACKEND_PORT` in `.env`. |
| Upload rejected although the file looks fine | Check the message: it names the real reason (size, page count, corrupt bytes, encryption). Glint validates content, not the extension. |
| `python` opens the Microsoft Store | That alias is not Python. Install from python.org or use `py -3.11`. |

## 13. Verification record (what was actually executed)

| Check | Result |
|---|---|
| `pytest` (94 mocked tests: API, validation, DB, analytics, regex) | **passed** |
| `pytest -m integration` (4 tests, real RapidOCR on CPU, incl. a real 2-page PDF through the API) | **passed** |
| `npx tsc --noEmit` | **passed** |
| `npm run build` (Vite production build, 299 KB JS / 92 KB gzip) | **passed** |
| Real OCR, invoice PNG with a table, email, dates, 5 amounts | **passed** — all fields recognized, 1.9 s |
| Real OCR, 3-page PDF, sequential rendering | **passed** — 3 pages, 10.3 s on a 2-core sandbox CPU |
| Error paths (unsupported, disguised, corrupt, oversized, empty, encrypted, >page-limit) | **passed** with correct 400/413/404/422/503 statuses |
| History search / delete / clear, analytics, chart PNG (data + empty) | **passed** |
| No temp-dir or original-document leftovers after requests | **verified** (`/tmp/glint-upload-*` empty; `backend/data/` contains only `glint.db`) |
| PowerShell scripts (`install.ps1`, `start.ps1`, `run-*.ps1`) | **NOT executed** — no PowerShell/Windows in this Linux sandbox; every command they invoke (`python -m venv`, `pip install -r`, `verify_ocr.py`, `python -m uvicorn`, `npm run dev/build`) was executed and verified directly here |
| Visual QA in a real browser (copy button click, drag-and-drop) | UI served and reviewed via the live preview; clipboard/drag behaviour relies on standard browser APIs with fallbacks |
