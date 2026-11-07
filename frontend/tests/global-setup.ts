import fs from 'node:fs';
import path from 'node:path';
import {
  ARTIFACT_DIR,
  E2E_DB_FILE,
  E2E_DB_PREFIX,
  E2E_DB_SUFFIX,
  E2E_RUN_ID,
  ensureArtifactDir,
} from './paths';

/**
 * Runs once before the tests.
 *
 * Note on ordering: Playwright starts `webServer` BEFORE globalSetup, so by
 * the time this function runs the backend is already up and has already
 * opened its database. Nothing here may therefore touch the CURRENT run's
 * database file - see the comment on E2E_DB_FILE in paths.ts. This function
 * only removes databases left behind by PREVIOUS runs, which no process has
 * open.
 */

/** Delete e2e databases from earlier runs. Never the current one. */
function removeStaleDatabases(): string[] {
  const current = path.basename(E2E_DB_FILE);
  const removed: string[] = [];

  let entries: string[];
  try {
    entries = fs.readdirSync(ARTIFACT_DIR);
  } catch {
    return removed;
  }

  for (const entry of entries) {
    const isOurs =
      entry.startsWith(E2E_DB_PREFIX) &&
      (entry.endsWith(E2E_DB_SUFFIX) ||
        entry.endsWith(`${E2E_DB_SUFFIX}-wal`) ||
        entry.endsWith(`${E2E_DB_SUFFIX}-shm`));
    if (!isOurs || entry.startsWith(current)) {
      continue;
    }
    try {
      fs.rmSync(path.join(ARTIFACT_DIR, entry), { force: true });
      removed.push(entry);
    } catch (error) {
      // A locked leftover is a warning, not a failure: this run uses its own
      // file and is unaffected. Reporting it honestly beats crashing.
      // eslint-disable-next-line no-console
      console.warn(`[global-setup] could not remove stale ${entry}: ${String(error)}`);
    }
  }
  return removed;
}

export default function globalSetup(): void {
  ensureArtifactDir();

  // eslint-disable-next-line no-console
  console.log(`[global-setup] run id    -> ${E2E_RUN_ID}`);
  // eslint-disable-next-line no-console
  console.log(`[global-setup] artifacts -> ${ARTIFACT_DIR}`);
  // eslint-disable-next-line no-console
  console.log(`[global-setup] database  -> ${E2E_DB_FILE}`);

  const removed = removeStaleDatabases();
  if (removed.length > 0) {
    // eslint-disable-next-line no-console
    console.log(`[global-setup] removed ${removed.length} stale database file(s)`);
  }
}
