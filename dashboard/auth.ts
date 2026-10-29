// Google sign-in inside the dashboard (U7, phase 11), with Auth.js. It is used only once AUTH_GOOGLE_ID,
// AUTH_GOOGLE_SECRET and AUTH_SECRET are set (lib/signin.ts signInEnabled); until then the dashboard keeps the name
// picker. Sessions are signed cookies that last SESSION_HOURS. Who may sign in: lib/signin.ts allowedSignIn.

import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import { parseUsers } from "@/lib/people";
import { allowedSignIn, SESSION_HOURS, signInDomain } from "@/lib/signin";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google({ authorization: { params: { prompt: "select_account", hd: signInDomain(process.env) } } })],
  session: { strategy: "jwt", maxAge: SESSION_HOURS * 3600 },
  pages: { signIn: "/login", error: "/login" },
  trustHost: true,
  callbacks: {
    signIn({ profile }) {
      const google = (profile ?? {}) as { email?: string | null; email_verified?: boolean; hd?: string | null };
      return allowedSignIn({ email: google.email ?? null, verified: google.email_verified === true, hd: google.hd ?? null },
        parseUsers(process.env.DASHBOARD_USERS), signInDomain(process.env)).ok;
    },
  },
});
