import type { Metadata, Viewport } from 'next';
import './globals.css';
import { AuthProvider } from '@/lib/auth-context';
import { ProjectProvider } from '@/lib/project-context';

export const metadata: Metadata = {
  title: 'Mem-Dog — Private AI System for Individuals & Organizations',
  description: 'Ingest data from 300+ apps, enrich with 42 AI agents, and query with 5 search modes powered by a temporal knowledge graph. Self-hosted, free, open source (Apache 2.0).',
  icons: {
    icon: '/favicon.ico',
  },
  openGraph: {
    title: 'Mem-Dog — Private AI System',
    description: 'Ingest from 300+ apps, enrich with 42 AI agents, query with 5 search modes. Self-hosted, free, Apache 2.0.',
    type: 'website',
    siteName: 'Mem-Dog',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
        {/* Background decorations */}
        <div className="fixed inset-0 overflow-hidden pointer-events-none">
          <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-500/20 rounded-full blur-3xl" />
          <div className="absolute top-1/2 -left-40 w-80 h-80 bg-accent-500/20 rounded-full blur-3xl" />
          <div className="absolute -bottom-40 right-1/3 w-80 h-80 bg-pink-500/20 rounded-full blur-3xl" />
        </div>
        
        {/* Main content */}
        <div className="relative z-10">
          <AuthProvider>
            <ProjectProvider>
              {children}
            </ProjectProvider>
          </AuthProvider>
        </div>
      </body>
    </html>
  );
}
