import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Email Tracker",
    short_name: "Mail",
    description: "The important mail from your Gmail accounts, job opportunities first.",
    start_url: "/",
    display: "standalone",
    background_color: "#f6f7f9",
    theme_color: "#2457c5",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
