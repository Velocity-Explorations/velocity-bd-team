import { LogIn } from "lucide-react";
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { signInAction } from "@/app/actions";
import { auth } from "@/auth";
import { loginMessage, safeFrom, signInEnabled } from "@/lib/signin";
import { firstParam } from "@/lib/text";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Sign in" };

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

/**
 * The BD Team sign-in page (U7, phase 11): the Velocity mark, Sign in with Google for the company's accounts on
 * DASHBOARD_USERS, Reset password (Google's account recovery) and Need access? There is no sign-up: an admin adds
 * people. It says in words why someone is here: signed out, timed out, not allowed or cancelled. Until the Google
 * client is set, it says sign-in is not set up and the dashboard keeps its name picker.
 */
export default async function LoginPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  const from = safeFrom(firstParam(sp.from, 500));
  const enabled = signInEnabled(process.env);
  if (enabled && (await auth())?.user) redirect(from);
  const message = enabled ? loginMessage({ reason: firstParam(sp.reason, 20), error: firstParam(sp.error, 60) }) : null;
  return (
    <main className="login">
      <section className="login-card" aria-labelledby="login-title">
        <h1 id="login-title" className="login-brand">
          <img src="/velocity-mark-white.png" alt="" width={40} height={30} />
          BD Team
        </h1>
        <p className="login-label">Sign in</p>
        <p className="login-hint">Use your Velocity Google account.</p>
        {message ? <p className="login-message" role="status">{message}</p> : null}
        {enabled ? (
          <form action={signInAction}>
            <input type="hidden" name="from" value={from} />
            <button type="submit" className="login-google">
              <LogIn aria-hidden="true" />
              Sign in with Google
            </button>
          </form>
        ) : (
          <p className="login-message">
            Sign-in is not set up yet. Until it is, choose your name at the top right of the dashboard.{" "}
            <a href="/">Open the dashboard</a>
          </p>
        )}
        <div className="login-links">
          <a href="https://accounts.google.com/signin/recovery" target="_blank" rel="noreferrer">Reset password</a>
          <span>Need access? Ask an admin</span>
        </div>
        <div className="login-band" aria-hidden="true" />
      </section>
    </main>
  );
}
