import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Providers from './providers';
import Link from 'next/link';
import SyncButton from '@/components/SyncButton';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Finance Dashboard',
  description: 'Local-first personal finance dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-background text-foreground antialiased min-h-screen flex flex-col`}>
        <Providers>
          {/* Top Bar Navigation Utility */}
          <header className="border-b border-muted/40 bg-background/50 backdrop-blur sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
              <div className="flex items-center space-x-8">
                <span className="font-bold tracking-tight text-lg bg-gradient-to-r from-emerald-400 to-cyan-500 bg-clip-text text-transparent">
                  VaultLocal
                </span>
                <nav className="flex items-center space-x-6 text-sm font-medium">
                  <Link href="/" className="text-muted-foreground hover:text-foreground transition-colors">
                    Dashboard
                  </Link>
                  <Link href="/transactions" className="text-muted-foreground hover:text-foreground transition-colors">
                    Transactions
                  </Link>
                </nav>
              </div>
              
              {/* Add the Sync button right here! */}
              <div className="flex items-center space-x-4">
                <SyncButton />
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" title="Local node active" />
              </div>
            </div>
          </header>

          <main className="max-w-7xl w-full mx-auto p-6 md:p-8 flex-1">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}