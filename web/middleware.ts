// Every page and server action needs a signed-in, allowed Google account,
// except the sign-in flow itself, the privacy page and static assets.
export { auth as middleware } from "@/auth";

export const config = {
  runtime: "nodejs",
  matcher: ["/((?!api/auth|signin|privacy|_next/static|_next/image|icon.svg|manifest.webmanifest|favicon.ico).*)"],
};
