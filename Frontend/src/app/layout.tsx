import { Inter, Newsreader } from "next/font/google";
import "./globals.css";
import { ReactQueryProvider } from "@/components/providers/ReactQueryProvider";
import { AppNavigation } from "@/components/navigation/AppNavigation";
import { ThemeProvider } from "@/components/theme-provider";
import { AuthProvider } from "@/context/AuthContext";
import { ToastProvider } from "@/context/ToastContext";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

// Titles only; everything a lawyer reads or fills in stays in Inter.
const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
});

export const metadata = {
  title: "EasyHuntV2",
  description: "Property document processing and review workspace",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${newsreader.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col bg-background text-foreground font-sans">
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          <ReactQueryProvider>
            <ToastProvider>
              <AuthProvider>
                <AppNavigation />
                {children}
              </AuthProvider>
            </ToastProvider>
          </ReactQueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
