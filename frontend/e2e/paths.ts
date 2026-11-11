import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

/**
 * Every path below is resolved from this file's own location, never from
 * process.cwd(). That is what makes `npx playwright test` work the same
 * whether it is launched from frontend/, from the repository root, or from a
 * freshly extracted ZIP where `artifacts/` does not exist yet.
 */

// frontend/e2e/paths.ts -> frontend/e2e -> frontend -> <repo root>
const TESTS_DIR = path.dirname(fileURLToPath(import.meta.url));
export const FRONTEND_DIR = path.resolve(TESTS_DIR, '..');
export const REPO_ROOT = path.resolve(FRONTEND_DIR, '..');
export const BACKEND_DIR = path.join(REPO_ROOT, 'backend');

export const PHASE = '7';

/**
 * Which environment produced the evidence. Defaults to `local-windows`
 * because that is the run the project owner performs by hand; CI overrides it
 * so the two sets of screenshots never overwrite each other.
 */
export const ARTIFACT_ENV = process.env['MS_ARTIFACT_ENV'] ?? 'local-windows';

export const ARTIFACT_DIR = path.join(REPO_ROOT, 'artifacts', `phase-${PHASE}`, ARTIFACT_ENV);

/** Create the artifact directory tree if it does not exist. Safe to call often. */
export function ensureArtifactDir(): string {
  fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
  return ARTIFACT_DIR;
}

/** Absolute path to a file inside the artifact directory, creating the dir. */
export function artifactPath(...parts: readonly string[]): string {
  ensureArtifactDir();
  return path.join(ARTIFACT_DIR, ...parts);
}

/**
 * Identifies one end-to-end run.
 *
 * Resolved from MS_E2E_RUN_ID when present and written back into
 * process.env otherwise, so every child process Playwright spawns - above all
 * the uvicorn `webServer` - inherits the same value.
 */
function resolveRunId(): string {
  const existing = process.env['MS_E2E_RUN_ID'];
  if (existing !== undefined && existing.trim() !== '') {
    return existing.trim();
  }
  const generated = `${Date.now().toString(36)}-${process.pid}`;
  process.env['MS_E2E_RUN_ID'] = generated;
  return generated;
}

export const E2E_RUN_ID = resolveRunId();

/** Glob-ish prefix/suffix used to find databases left by *previous* runs. */
export const E2E_DB_PREFIX = 'e2e-phase7-';
export const E2E_DB_SUFFIX = '.sqlite3';

/**
 * The SQLite database for THIS run. Never the developer's dev database, and
 * never shared with a previous run.
 *
 * The filename carries the run id on purpose. Playwright starts `webServer`
 * BEFORE `globalSetup` runs (verified by log ordering), so a fixed filename
 * meant globalSetup was deleting a database file that the freshly started
 * uvicorn process already had open. On Linux that silently succeeds - the
 * inode is unlinked and the server keeps writing to a file nobody can see.
 * On Windows, SQLite opens the file without FILE_SHARE_DELETE, so the same
 * delete would raise a sharing violation and abort the whole run.
 *
 * A unique name per run sidesteps both: the file cannot pre-exist, so it is
 * always empty, so nothing has to be deleted while it is open.
 */
export const E2E_DB_FILE = path.join(
  ARTIFACT_DIR,
  `${E2E_DB_PREFIX}${E2E_RUN_ID}${E2E_DB_SUFFIX}`,
);

/**
 * Fixed ports, deliberately.
 *
 * 8010 - the end-to-end server (FastAPI serving the built SPA).
 * 5174 - the Vite dev server, used only by `npm run dev`.
 *
 * They are fixed rather than random so that a stuck process is findable:
 *   Get-NetTCPConnection -LocalPort 8010,5174
 *
 * Always 127.0.0.1, never `localhost`. On Windows, Node may resolve
 * `localhost` to ::1 while a server bound to IPv4 is listening on 127.0.0.1,
 * which produces an ECONNREFUSED that looks like the server failed to start.
 * Using the literal IPv4 address removes that whole class of confusion.
 * (This limits exposure to the local machine. It does not and cannot
 * guarantee that Windows Firewall will never interfere.)
 */
export const E2E_HOST = '127.0.0.1';

function readPort(raw: string | undefined, fallback: number): number {
  if (raw === undefined || raw.trim() === '') {
    return fallback;
  }
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    // A typo like MS_E2E_PORT=80l0 would otherwise become NaN and surface as
    // an unreadable connection error much later.
    throw new Error(
      `MS_E2E_PORT must be an integer between 1 and 65535, got "${raw}".`,
    );
  }
  return parsed;
}

export const E2E_PORT = readPort(process.env['MS_E2E_PORT'], 8010);
export const E2E_BASE_URL = `http://${E2E_HOST}:${E2E_PORT}`;

/** Vite dev-server port. Not used by the Playwright run. */
export const DEV_PORT = 5174;
