import path from "node:path";

/** IANA zone for every displayed time. The ledger itself stores UTC. */
export function displayTimeZone(): string {
  return process.env.DASHBOARD_TIMEZONE?.trim() || "America/Denver";
}

/**
 * Directory the pipeline writes run logs to; /runs/<id>/log serves files from here only.
 * The logs live outside the app, so the bundler is told not to trace this path.
 */
export function logsDir(): string {
  const configured = process.env.LEDGER_LOG_DIR?.trim();
  return path.resolve(/*turbopackIgnore: true*/ configured || path.join(process.cwd(), "..", "data", "logs"));
}
