// Google sign-in inside the dashboard (U7, phase 11), with Auth.js. It is used only once AUTH_GOOGLE_ID,
// AUTH_GOOGLE_SECRET and AUTH_SECRET are set (lib/signin.ts signInEnabled); until then the dashboard keeps the name
// picker. Sessions are signed cookies that last SESSION_HOURS. Any Velocity Google account may sign in (lib/signin.ts
// allowedSignIn); each sign-in is recorded in the people table (lib/team.ts), which names the person from then on.

import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { allowedSignIn, SESSION_HOURS, signInDomain } from "@/lib/signin";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google({ authorization: { params: { prompt: "select_account", hd: signInDomain(process.env) } } })],
  session: { strategy: "jwt", maxAge: SESSION_HOURS * 3600 },
  pages: { signIn: "/login", error: "/login" },
  trustHost: true,
  callbacks: {
    async signIn({ profile }) {
      const google = (profile ?? {}) as { email?: string | null; email_verified?: boolean; hd?: string | null; name?: string | null };
      if (!allowedSignIn({ email: google.email ?? null, verified: google.email_verified === true, hd: google.hd ?? null },
        signInDomain(process.env))) return false;
      const { recordSignIn } = await import("@/lib/team");   // only here, so the proxy never loads the database
      await recordSignIn(String(google.email), google.name ?? null);
      return true;
    },
  },
});
