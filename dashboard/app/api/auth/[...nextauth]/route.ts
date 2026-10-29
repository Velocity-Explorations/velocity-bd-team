// Auth.js's own routes: the Google redirect, its callback, the session and sign-out (phase 11). While sign-in is not
// set up they answer not found, rather than an error about the missing settings.
import type { NextRequest } from "next/server";
import { handlers } from "@/auth";
import { signInEnabled } from "@/lib/signin";

function off(): Response {
  return new Response("Sign-in is not set up.", { status: 404, headers: { "content-type": "text/plain; charset=utf-8" } });
}

export async function GET(request: NextRequest): Promise<Response> {
  return signInEnabled(process.env) ? handlers.GET(request) : off();
}

export async function POST(request: NextRequest): Promise<Response> {
  return signInEnabled(process.env) ? handlers.POST(request) : off();
}
