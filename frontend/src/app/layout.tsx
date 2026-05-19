import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LaunchLens — Validate Your Product Idea Before You Build",
  description: "Validate your product idea before you build. LaunchLens uses AI agents to research real community conversations and score your product-market fit in under 90 seconds.",
  openGraph: {
    title: "LaunchLens — Validate Your Product Idea Before You Build",
    description: "Validate your product idea before you build. LaunchLens uses AI agents to research real community conversations and score your product-market fit in under 90 seconds.",
    url: "https://launch-lens-now.vercel.app",
    siteName: "LaunchLens",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "LaunchLens — Validate Your Product Idea Before You Build",
    description: "Validate your product idea before you build. LaunchLens uses AI agents to research real community conversations and score your product-market fit in under 90 seconds.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
