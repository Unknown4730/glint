import {
  Boxes,
  CheckCircle2,
  Cpu,
  Database,
  FileCode2,
  Globe,
  GraduationCap,
  HardDrive,
  Lock,
  Server,
  Terminal,
  TriangleAlert,
} from 'lucide-react'
import type { Health } from '../types'
import { Badge } from '../components/Badge'
import { Panel } from '../components/Panel'

const ARCHITECTURE = [
  {
    icon: FileCode2,
    title: 'React + Vite UI',
    detail:
      'TypeScript, Tailwind CSS and Lucide icons. One API client module (services/api.ts) performs every request.',
    tag: 'frontend/',
  },
  {
    icon: Server,
    title: 'FastAPI backend',
    detail:
      'Synchronous routes for CPU-bound work, so the event loop is never blocked. One consistent JSON error shape.',
    tag: 'backend/app/main.py',
  },
  {
    icon: Cpu,
    title: 'RapidOCR + ONNX Runtime',
    detail:
      'PP-OCRv6 "small" detection/recognition models run on the CPU. The engine is created once and reused behind a lock.',
    tag: 'backend/app/ocr_service.py',
  },
  {
    icon: Database,
    title: 'SQLite history',
    detail:
      'Extracted text and metadata only, written with parameterized queries through the standard library sqlite3 module.',
    tag: 'backend/app/database.py',
  },
]

const CONCEPTS = [
  { concept: 'Python fundamentals', where: 'Functions, conditions, dictionaries and loops across every backend module.' },
  { concept: 'Exception handling', where: 'document_service.py maps each failure to an HTTP status and a short code.' },
  { concept: 'File handling', where: 'Uploads are streamed into a temporary directory that is always removed in a finally block.' },
  { concept: 'Object-oriented programming', where: 'OCRService in ocr_service.py owns engine creation, warm-up and the run lock.' },
  { concept: 'Regular expressions', where: 'text_utils.py extracts emails, date-like strings and currency amounts.' },
  { concept: 'Pandas', where: 'analytics_service.py aggregates the history rows into the metrics you see in Analytics.' },
  { concept: 'NumPy', where: 'brightness_stats() turns a small thumbnail into an array to warn about dark or blank pages.' },
  { concept: 'Matplotlib', where: 'One PNG chart rendered with the non-interactive Agg backend, styled to match the UI.' },
  { concept: 'SQLite', where: 'database.py creates the schema on start-up and stores every finished job.' },
  { concept: 'PyMuPDF + Pillow', where: 'PDF pages are rendered one at a time; images are verified, EXIF-corrected and resized.' },
]

const LIMITATIONS = [
  'Optimized for ordinary printed text and document scans — not handwriting, music notation or complex tables.',
  'Layout is not reconstructed: multi-column pages come back as reading-order lines, not as a formatted document.',
  'One document at a time. PDF pages are processed sequentially on purpose, to stay inside 8 GB of RAM.',
  'Password-protected PDFs are rejected rather than decrypted.',
  'Language support follows the bundled PP-OCRv6 model (Latin scripts plus Chinese); other scripts need a different model.',
  'The first installation needs internet access to install Python packages. OCR itself then runs offline, because the models ship inside the rapidocr wheel.',
]

export interface AboutPageProps {
  health: Health | null
}

export function AboutPage({ health }: AboutPageProps) {
  const limits = health?.limits

  return (
    <div className="space-y-5">
      {/* hero ------------------------------------------------------------ */}
      <div className="relative overflow-hidden rounded-card border border-line bg-surface px-6 py-8 shadow-panel">
        <div
          className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-lime/[0.08] blur-2xl"
          aria-hidden="true"
        />
        <div className="relative max-w-2xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-lime">
            See beyond the page
          </p>
          <h1 className="mt-3 text-[30px] font-semibold leading-tight tracking-tight text-ink">
            Glint is a lightweight local OCR and document digitization system.
          </h1>
          <p className="mt-3 text-[14px] leading-relaxed text-muted">
            Simple on the surface, reliable underneath. Glint converts document images and PDF
            pages into editable text with a compact OCR model that runs on your CPU. There is no
            account, no cloud service, no API key and no upload of your documents anywhere.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Badge tone="lime">
              <Cpu className="h-3 w-3" aria-hidden="true" /> CPU only
            </Badge>
            <Badge>
              <Lock className="h-3 w-3" aria-hidden="true" /> Offline after install
            </Badge>
            <Badge>
              <HardDrive className="h-3 w-3" aria-hidden="true" /> Tuned for 8 GB RAM
            </Badge>
            <Badge>v{health?.version ?? '1.0.0'}</Badge>
          </div>
        </div>
      </div>

      {/* architecture ---------------------------------------------------- */}
      <Panel
        title="Architecture"
        subtitle="Four small layers, no queues, no microservices, no containers."
        icon={<Boxes />}
      >
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {ARCHITECTURE.map((layer, index) => {
            const Icon = layer.icon
            return (
              <div
                key={layer.title}
                className="rounded-xl border border-line bg-raised/60 p-4 transition-colors hover:border-[#3a404b]"
              >
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-line bg-surface text-lime">
                    <Icon className="h-[17px] w-[17px]" aria-hidden="true" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[13.5px] font-semibold text-ink">
                      <span className="mr-1.5 text-[11px] font-medium text-faint tabular-nums">
                        {index + 1}
                      </span>
                      {layer.title}
                    </p>
                    <p className="truncate font-mono text-[11px] text-faint">{layer.tag}</p>
                  </div>
                </div>
                <p className="mt-2.5 text-[12.5px] leading-relaxed text-muted">{layer.detail}</p>
              </div>
            )
          })}
        </div>

        <div className="mt-4 rounded-xl border border-line bg-canvas/60 p-4">
          <p className="text-[12px] font-medium uppercase tracking-[0.07em] text-faint">
            One request, end to end
          </p>
          <p className="mt-2 font-mono text-[12px] leading-relaxed text-muted">
            browser → <span className="text-ink">POST /api/ocr</span> → validate size + sniff real
            content type → <span className="text-ink">temp dir</span> → render pages sequentially →{' '}
            <span className="text-lime">RapidOCR (ONNX, CPU)</span> → normalize + regex patterns →{' '}
            <span className="text-ink">SQLite</span> → JSON response → temp dir deleted
          </p>
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* limits -------------------------------------------------------- */}
        <Panel title="Processing limits" subtitle="Configurable in backend/app/config.py" icon={<TriangleAlert />}>
          <dl className="divide-y divide-line-soft">
            {[
              { label: 'Maximum file size', value: limits ? `${limits.max_file_size_mb} MB` : '10 MB' },
              { label: 'Maximum PDF pages', value: limits ? `${limits.max_pdf_pages} pages` : '10 pages' },
              { label: 'Maximum image side', value: limits ? `${limits.max_image_side_px} px` : '3000 px' },
              { label: 'PDF render resolution', value: limits ? `${limits.pdf_render_dpi} DPI` : '150 DPI' },
              {
                label: 'Accepted formats',
                value: limits ? limits.accepted_extensions.join(', ') : '.pdf, .png, .jpg, .jpeg, .webp',
              },
              { label: 'OCR engine', value: health?.ocr.model ?? 'PP-OCRv6 small' },
              {
                label: 'Runtime',
                value: health?.ocr.runtime_version
                  ? `ONNX Runtime ${health.ocr.runtime_version} (CPU)`
                  : 'ONNX Runtime (CPU)',
              },
            ].map((row) => (
              <div key={row.label} className="flex items-baseline justify-between gap-4 py-2.5">
                <dt className="text-[12.5px] text-muted">{row.label}</dt>
                <dd className="text-right text-[12.5px] font-medium text-ink">{row.value}</dd>
              </div>
            ))}
          </dl>
        </Panel>

        {/* privacy ------------------------------------------------------- */}
        <Panel title="Privacy and offline behaviour" icon={<Lock />}>
          <ul className="space-y-2.5">
            {[
              'Documents never leave this computer. No cloud OCR, no telemetry, no third-party API.',
              'The uploaded file is written to a temporary directory and deleted when the request ends — even if processing fails.',
              'Only extracted text and metadata are stored, in backend/data/glint.db.',
              'History can be deleted entry by entry or cleared completely from the History screen.',
              'Full document text is never written to the backend log.',
              'The dev servers bind to localhost by default; nothing is exposed publicly without an explicit configuration change.',
            ].map((line) => (
              <li key={line} className="flex gap-2.5 text-[12.5px] leading-relaxed text-muted">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 rounded-lg border border-warning/25 bg-warning/[0.07] px-3 py-2.5 text-[12px] leading-relaxed text-muted">
            <span className="font-medium text-ink">First install needs internet.</span> Python and
            Node packages are downloaded once. The PP-OCRv6 models ship inside the{' '}
            <code className="font-mono text-ink">rapidocr</code> wheel, so after installation OCR
            runs with the network switched off.
          </p>
        </Panel>
      </div>

      {/* known limitations ----------------------------------------------- */}
      <Panel title="Known limitations" subtitle="Honest boundaries of the MVP" icon={<TriangleAlert />}>
        <ul className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
          {LIMITATIONS.map((line) => (
            <li
              key={line}
              className="flex gap-2.5 rounded-lg border border-line-soft bg-raised/40 px-3 py-2.5 text-[12.5px] leading-relaxed text-muted"
            >
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-warning/80" aria-hidden="true" />
              <span>{line}</span>
            </li>
          ))}
        </ul>
      </Panel>

      {/* academic mapping ------------------------------------------------ */}
      <Panel
        title="Concept map"
        subtitle="Where each programming concept actually appears in this codebase."
        icon={<GraduationCap />}
      >
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-[0.07em] text-faint">
                <th className="py-2 pr-4 font-medium">Concept</th>
                <th className="py-2 font-medium">Implemented in</th>
              </tr>
            </thead>
            <tbody>
              {CONCEPTS.map((row) => (
                <tr key={row.concept} className="border-b border-line-soft last:border-0">
                  <td className="py-2.5 pr-4 align-top text-[12.5px] font-medium text-ink">
                    {row.concept}
                  </td>
                  <td className="py-2.5 align-top text-[12.5px] leading-relaxed text-muted">
                    {row.where}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {/* developer commands ---------------------------------------------- */}
      <Panel title="Run it yourself" subtitle="Windows PowerShell, from the project root" icon={<Terminal />}>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {[
            { label: 'Install everything', command: '.\\install.ps1' },
            { label: 'Start backend + frontend', command: '.\\start.ps1' },
            { label: 'Backend only', command: '.\\run-backend.ps1' },
            { label: 'Frontend only', command: '.\\run-frontend.ps1' },
            { label: 'Backend tests (fast, mocked OCR)', command: 'cd backend; ..\\.venv\\Scripts\\python -m pytest' },
            { label: 'Real OCR smoke tests', command: 'cd backend; ..\\.venv\\Scripts\\python -m pytest -m integration' },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-line bg-canvas/60 px-3.5 py-3">
              <p className="text-[11.5px] uppercase tracking-[0.06em] text-faint">{item.label}</p>
              <code className="mt-1.5 block font-mono text-[12.5px] text-lime">{item.command}</code>
            </div>
          ))}
        </div>
        <p className="mt-3.5 flex items-start gap-2 text-[12px] leading-relaxed text-muted">
          <Globe className="mt-0.5 h-4 w-4 shrink-0 text-faint" aria-hidden="true" />
          Frontend: http://localhost:5173 · Backend API: http://127.0.0.1:8000 · Interactive API
          docs: http://127.0.0.1:8000/api/docs
        </p>
      </Panel>
    </div>
  )
}
