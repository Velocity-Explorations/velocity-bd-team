import { promises as fs } from "node:fs";
import path from "node:path";
import { runLogPath } from "@/lib/queries";
import { logsDir } from "@/lib/settings";

// Serves a run's log file, but only from the pipeline's log directory on this machine. On a
// host that does not have the logs (a cloud deployment), it says so instead.

export const dynamic = "force-dynamic";

function text(status: number, body: string): Response {
  return new Response(body, { status, headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" } });
}

function inside(file: string, dir: string): boolean {
  const a = path.resolve(file);
  const b = dir.endsWith(path.sep) ? dir : dir + path.sep;
  return process.platform === "win32" ? a.toLowerCase().startsWith(b.toLowerCase()) : a.startsWith(b);
}

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }): Promise<Response> {
  const { id } = await context.params;
  if (!/^\d{1,9}$/.test(id)) return text(400, "Run ids are whole numbers.");
  const logPath = await runLogPath(Number(id));
  if (!logPath) return text(404, `Run ${id} has no log path recorded.`);
  const dir = logsDir();
  if (!logPath.endsWith(".log") || !inside(logPath, dir)) {
    return text(403, `Not served: ${logPath} is outside the log directory ${dir}.`);
  }
  try {
    return new Response(await fs.readFile(path.resolve(logPath), "utf8"), {
      headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
    });
  } catch {
    return text(404, `The log is not on this host: ${logPath}`);
  }
}
