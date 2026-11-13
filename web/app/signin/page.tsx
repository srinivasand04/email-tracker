import { signIn } from "@/auth";

export const metadata = { title: "Sign in · Email Tracker" };

const MESSAGES: Record<string, string> = {
  AccessDenied: "That Google account is not allowed. Sign in with one of your own tracked addresses.",
  Configuration: "Sign-in is not set up on this server yet.",
};

export default async function SignIn({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; callbackUrl?: string }>;
}) {
  const { error, callbackUrl } = await searchParams;
  // Only same-site paths, never an outside URL
  const redirectTo = callbackUrl?.startsWith("/") && !callbackUrl.startsWith("//") ? callbackUrl : "/";

  return (
    <main className="signin">
      <h1>Email Tracker</h1>
      <p className="meta">Private dashboard. Sign in with one of your own Google accounts.</p>
      {error && <p className="warning">{MESSAGES[error] ?? "Sign-in failed. Try again."}</p>}
      <form
        action={async () => {
          "use server";
          await signIn("google", { redirectTo });
        }}
      >
        <button type="submit">Sign in with Google</button>
      </form>
      <p className="meta">
        <a href="/privacy">Privacy</a>
      </p>
    </main>
  );
}
