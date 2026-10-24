import path from "node:path";
import { cookies } from "next/headers";
import { COLUMNS_COOKIE, readHidden, type Hidden } from "./columns";
import { pickQueueMode, type QueueMode } from "./values";

/** Whether everyone decides every call in the review queue (see pickQueueMode). */
export function queueMode(): QueueMode {
  return pickQueueMode(process.env.DASHBOARD_QUEUE);
}

/** The columns this browser has hidden in the Settings dialog (PRO-555). */
export async function hiddenColumns(): Promise<Hidden> {
  return readHidden((await cookies()).get(COLUMNS_COOKIE)?.value);
}

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
