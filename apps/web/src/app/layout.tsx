import type { Metadata } from "next";
import { AppHeader } from "@/components/shell/AppHeader";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Strategic Investigation Platform",
    template: "%s · Strategic Investigation Platform",
  },
  description: "Autonomous research. Governed reasoning. Human decisions.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="min-h-dvh antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <AppHeader />
        <main id="main">{children}</main>
      </body>
    </html>
  );
}
