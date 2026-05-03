'use client';

import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { ArrowLeft, Package, AlertCircle, Loader2, Sparkles, Copy, Check, Link } from 'lucide-react';
import Sidebar from '@/components/Sidebar';
import type { TabId } from '@/components/Sidebar';
import DataViewer from '@/components/DataViewer';
import VersionHistory from '@/components/VersionHistory';
import DataAI from '@/components/DataAI';
import type { DataMetadata } from '@/types';
import { getMetadata } from '@/lib/api';

export default function DataDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params?.id as string;

  const [metadata, setMetadata] = useState<DataMetadata | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [addressCopied, setAddressCopied] = useState(false);

  useEffect(() => {
    loadMetadata();
  }, [id]);

  const loadMetadata = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getMetadata(id);
      setMetadata(data);
      setSelectedVersion(data.current_version);
    } catch (err: any) {
      setError(err.message || 'Failed to load metadata');
    } finally {
      setLoading(false);
    }
  };

  const handleVersionSelect = (version: number) => {
    setSelectedVersion(version);
  };

  const handleUpdate = () => {
    loadMetadata();
  };

  const handleDelete = () => {
    router.push('/');
  };

  const copyId = async () => {
    await navigator.clipboard.writeText(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleNavChange = (tab: TabId) => {
    router.push(`/?tab=${tab}`);
  };

  if (loading) {
    return (
      <main className="flex h-screen overflow-hidden">
        <Sidebar activeTab="data" onTabChange={handleNavChange} />
        <div className="flex-1 flex items-center justify-center">
          <div className="glass-card p-16">
            <div className="flex flex-col items-center justify-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
                <Loader2 className="w-8 h-8 text-white animate-spin" />
              </div>
              <p className="text-white/60 text-lg">Loading data details...</p>
            </div>
          </div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex h-screen overflow-hidden">
        <Sidebar activeTab="data" onTabChange={handleNavChange} />
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="glass-card p-12 max-w-lg w-full">
            <div className="flex flex-col items-center justify-center gap-6 text-center">
              <div className="w-20 h-20 rounded-2xl bg-red-500/20 flex items-center justify-center">
                <AlertCircle className="w-10 h-10 text-red-400" />
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white mb-2">Error Loading Data</h2>
                <p className="text-red-400">{error}</p>
              </div>
              <button
                onClick={() => router.push('/')}
                className="btn-secondary flex items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to Home
              </button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  if (!metadata || !metadata.versions) {
    return (
      <main className="flex h-screen overflow-hidden">
        <Sidebar activeTab="data" onTabChange={handleNavChange} />
        <div className="flex-1 flex items-center justify-center px-6">
          <div className="glass-card p-12 max-w-lg w-full">
            <div className="flex flex-col items-center justify-center gap-4 text-center">
              <div className="w-20 h-20 rounded-2xl bg-amber-500/20 flex items-center justify-center">
                <Package className="w-10 h-10 text-amber-400" />
              </div>
              <h2 className="text-2xl font-bold text-white">Data Not Found</h2>
              <p className="text-white/50">The requested data could not be found</p>
              <button
                onClick={() => router.push('/')}
                className="btn-premium flex items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Back to Home</span>
              </button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex h-screen overflow-hidden">
      <Sidebar activeTab="data" onTabChange={handleNavChange} />

      {/* Main content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Header */}
        <header className="flex-shrink-0 border-b border-white/10 bg-white/5 backdrop-blur-xl">
          <div className="px-6 py-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center gap-4">
                {/* Back Button */}
                <button
                  onClick={() => router.push('/')}
                  className="w-10 h-10 rounded-xl border border-white/20 bg-white/5 flex items-center justify-center text-white/60 hover:text-white hover:bg-white/10 transition-all"
                >
                  <ArrowLeft className="w-5 h-5" />
                </button>

                {/* Title */}
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
                      <Sparkles className="w-4 h-4 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-white">Data Details</h1>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-white/40">ID:</span>
                    <code className="text-xs text-primary-400 bg-primary-500/10 px-2 py-1 rounded-md font-mono">
                      {id.substring(0, 24)}...
                    </code>
                    <button
                      onClick={copyId}
                      className="p-1 rounded-md hover:bg-white/10 transition-colors"
                      title="Copy full ID"
                    >
                      {copied ? (
                        <Check className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <Copy className="w-4 h-4 text-white/40 hover:text-white/60" />
                      )}
                    </button>
                  </div>
                  {metadata?.address && (
                    <div className="flex items-center gap-2 mt-1">
                      <Link className="w-3.5 h-3.5 text-teal-400/60" />
                      <a
                        href={metadata.address}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-teal-400/80 hover:text-teal-300 font-mono truncate max-w-[300px] transition-colors"
                        title={metadata.address}
                      >
                        {metadata.address}
                      </a>
                      <button
                        onClick={async () => {
                          if (metadata.address) {
                            await navigator.clipboard.writeText(metadata.address);
                            setAddressCopied(true);
                            setTimeout(() => setAddressCopied(false), 2000);
                          }
                        }}
                        className="p-1 rounded-md hover:bg-white/10 transition-colors"
                        title="Copy address"
                      >
                        {addressCopied ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5 text-white/40 hover:text-white/60" />
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Stats */}
              <div className="flex items-center gap-4">
                <div className="px-4 py-2 rounded-xl bg-white/5 border border-white/10">
                  <span className="text-sm text-white/50">Versions:</span>
                  <span className="ml-2 text-white font-semibold">{metadata.versions.length}</span>
                </div>
                <div className="px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30">
                  <span className="text-sm text-emerald-400/70">Current:</span>
                  <span className="ml-2 text-emerald-400 font-semibold">v{metadata.current_version}</span>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-6 py-8">
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
              <div className="animate-in">
                <DataAI dataId={id} />
                <DataViewer
                  dataId={id}
                  version={selectedVersion}
                  metadata={metadata}
                  onUpdate={handleUpdate}
                  onDelete={handleDelete}
                />
              </div>
              <div className="animate-in stagger-1">
                <VersionHistory
                  versions={metadata.versions}
                  currentVersion={metadata.current_version}
                  selectedVersion={selectedVersion}
                  onVersionSelect={handleVersionSelect}
                />
              </div>
            </div>
          </div>

          {/* Footer */}
          <footer className="border-t border-white/10 mt-8">
            <div className="px-6 py-4 flex items-center justify-between text-sm text-white/40">
              <p>Powered by Google Cloud Storage</p>
              <p>Built with Next.js + Tailwind CSS</p>
            </div>
          </footer>
        </div>
      </div>
    </main>
  );
}
