import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";

import { AppSidebar } from "@/components/app-sidebar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "QA Testing Agent", template: "%s · QA Testing Agent" },
  description: "Local QA dashboard: Quick Scan and Claude Code agents against your app on localhost.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col md:flex-row">
        <Suspense fallback={<div className="border-b bg-sidebar md:h-screen md:w-64 md:border-r" />}>
          <AppSidebar />
        </Suspense>
        <main id="main" className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8">
          <div className="mx-auto max-w-5xl">{children}</div>
        </main>
      </body>
    </html>
  );
}
