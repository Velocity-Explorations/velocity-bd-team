// The load balancer's health check. It answers without the database or the sign-in, so a
// database outage shows as an error page instead of taking the dashboard offline.

export const dynamic = "force-dynamic";

export function GET(): Response {
  return new Response("ok", { headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" } });
}
