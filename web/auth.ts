import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

/** Only these Google accounts may open the dashboard (ALLOWED_EMAILS, comma-separated). */
export function allowedEmails(): string[] {
  return (process.env.ALLOWED_EMAILS ?? "")
    .split(",")
    .map((email) => email.trim().toLowerCase())
    .filter(Boolean);
}

export function isAllowed(email: string | null | undefined): boolean {
  return Boolean(email) && allowedEmails().includes(email!.toLowerCase());
}

// Reads AUTH_SECRET, AUTH_GOOGLE_ID and AUTH_GOOGLE_SECRET from the environment.
export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [Google],
  trustHost: true, // served by Vercel or on 127.0.0.1 only
  session: { strategy: "jwt", maxAge: 30 * 24 * 60 * 60 },
  pages: { signIn: "/signin", error: "/signin" },
  callbacks: {
    // Refuse every Google account that is not on the list, before a session exists.
    signIn({ profile }) {
      return Boolean(profile?.email_verified) && isAllowed(profile?.email);
    },
    // Used by the middleware for every protected request.
    authorized({ auth: session }) {
      return isAllowed(session?.user?.email);
    },
  },
});

/** For server actions: throws unless the caller is signed in with an allowed account. */
export async function requireUser(): Promise<string> {
  const session = await auth();
  const email = session?.user?.email;
  if (!isAllowed(email)) throw new Error("Not signed in");
  return email!;
}
