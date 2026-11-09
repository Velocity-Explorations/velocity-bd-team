// A person's profile picture (David, 9 Nov 2026): /api/picture?name=David%20Wood&v=<when it was set>. Every picture was
// re-encoded by the dashboard on upload, so this only ever sends a WebP it made. Behind sign-in like every other page.

import { readPicture } from "@/lib/queries";

export const dynamic = "force-dynamic";

const NOT_FOUND = { status: 404, headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" } };

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const name = (url.searchParams.get("name") ?? "").trim().slice(0, 120);
  const row = name ? await readPicture(name).catch(() => null) : null;
  if (!row || row.content_type !== "image/webp") return new Response("No picture", NOT_FOUND);
  const current = url.searchParams.get("v") === row.updated_at;   // an address naming this picture never changes
  return new Response(new Uint8Array(Buffer.from(row.picture, "base64")), {
    headers: {
      "content-type": "image/webp",
      "cache-control": current ? "private, max-age=31536000, immutable" : "private, no-cache",
      "x-content-type-options": "nosniff",
      "content-security-policy": "default-src 'none'; sandbox",
    },
  });
}
