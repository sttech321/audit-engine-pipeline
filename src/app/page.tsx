'use client';

import Link from 'next/link';
import { WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import { Shield, Upload, CheckCircle, Coins, ArrowRight, ChevronRight } from 'lucide-react';

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 dark:from-gray-900 dark:via-blue-950 dark:to-purple-950">
      {/* Header */}
      <header className="border-b border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Shield className="w-8 h-8 text-blue-600" />
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                Audit NFT Minter
              </h1>
            </div>
            <WalletMultiButton className="!bg-blue-600 hover:!bg-blue-700" />
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h2 className="text-5xl md:text-6xl font-bold text-gray-900 dark:text-gray-100 mb-6">
            Cryptographic Audit
            <br />
            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Verification & NFT Minting
            </span>
          </h2>
          <p className="text-xl text-gray-600 dark:text-gray-400 max-w-3xl mx-auto mb-8">
            Upload, verify, and mint cryptographic audit artifacts as NFTs on Solana.
            Ensure provenance and integrity with deterministic verification.
          </p>
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold rounded-xl transition-all shadow-lg hover:shadow-xl hover:scale-[1.02]"
          >
            <Upload className="w-5 h-5" />
            Upload Audit File
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>

        {/* How It Works - Process Overview */}
        <div className="mb-16">
          <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4 text-center">
            How It Works
          </h3>
          <p className="text-gray-600 dark:text-gray-400 text-center max-w-2xl mx-auto mb-10">
            Your file flows through three stages. Each step is deterministic—same file always produces the same result.
          </p>
        </div>

        {/* Process Steps - Enhanced with flow arrows */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-6 mb-16">
          {/* Step 1 */}
          <div className="group relative bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-xl border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-2xl transition-all duration-300">
            <div className="absolute top-6 right-6 w-8 h-8 rounded-full bg-blue-600 text-white text-sm font-bold flex items-center justify-center">
              1
            </div>
            <div className="w-14 h-14 bg-blue-100 dark:bg-blue-900 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Upload className="w-7 h-7 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-3">
              Upload & Analyze
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Drop your audit artifact—we support <span className="font-mono text-sm">.lm3z</span>, <span className="font-mono text-sm">.rim0</span>, and <span className="font-mono text-sm">.rim95</span> formats.
            </p>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <li className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                <span>RIM-OS v2 splits the file into 1 MB chunks and runs the audit pipeline</span>
              </li>
              <li className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                <span>You get KPIs: integrity score, anomaly count, KAG separability, Penrose match</span>
              </li>
              <li className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
                <span>Large files (100+ MB) use parallel chunked upload—progress shown in real time</span>
              </li>
            </ul>
            <div className="hidden md:flex absolute -right-8 top-1/2 -translate-y-1/2 z-10 text-gray-300 dark:text-gray-500">
              <ArrowRight className="w-6 h-6" />
            </div>
          </div>

          {/* Step 2 */}
          <div className="group relative bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-xl border border-gray-200 dark:border-gray-700 hover:border-green-300 dark:hover:border-green-700 hover:shadow-2xl transition-all duration-300">
            <div className="absolute top-6 right-6 w-8 h-8 rounded-full bg-green-600 text-white text-sm font-bold flex items-center justify-center">
              2
            </div>
            <div className="w-14 h-14 bg-green-100 dark:bg-green-900 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <CheckCircle className="w-7 h-7 text-green-600 dark:text-green-400" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-3">
              Verify Cryptographically
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Every audit is deterministic—same input always yields the same verification.
            </p>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <li className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                <span>SHA-256 hash of the file serves as the canonical fingerprint</span>
              </li>
              <li className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                <span>Ed25519 signature check when your artifact includes signed metadata</span>
              </li>
              <li className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-green-500 shrink-0 mt-0.5" />
                <span>Risk level: LOW (score ≥90), MEDIUM (70–89), HIGH (&lt;70)</span>
              </li>
            </ul>
            <div className="hidden md:flex absolute -right-8 top-1/2 -translate-y-1/2 z-10 text-gray-300 dark:text-gray-500">
              <ArrowRight className="w-6 h-6" />
            </div>
          </div>

          {/* Step 3 */}
          <div className="group relative bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-xl border border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-700 hover:shadow-2xl transition-all duration-300">
            <div className="absolute top-6 right-6 w-8 h-8 rounded-full bg-purple-600 text-white text-sm font-bold flex items-center justify-center">
              3
            </div>
            <div className="w-14 h-14 bg-purple-100 dark:bg-purple-900 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
              <Coins className="w-7 h-7 text-purple-600 dark:text-purple-400" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-3">
              Mint as NFT
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Turn your audit result into a provable on-chain token.
            </p>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <li className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-purple-500 shrink-0 mt-0.5" />
                <span>Connect your Solana wallet and mint in one click</span>
              </li>
              <li className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-purple-500 shrink-0 mt-0.5" />
                <span>Metadata stored on IPFS; verification hash embedded on-chain</span>
              </li>
              <li className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-purple-500 shrink-0 mt-0.5" />
                <span>NFT proves provenance—no model weights or raw data ever stored</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Core Principles */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-xl border border-gray-200 dark:border-gray-700">
          <h3 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2 text-center">
            Core Principles
          </h3>
          <p className="text-gray-600 dark:text-gray-400 text-center text-sm mb-8 max-w-xl mx-auto">
            We verify integrity without touching your model. Here&apos;s what we do—and what we never do.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="flex items-start gap-3 p-4 rounded-xl bg-green-50/50 dark:bg-green-950/20 border border-green-100 dark:border-green-900/50">
              <div className="w-6 h-6 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center flex-shrink-0 mt-1">
                <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="font-semibold text-gray-900 dark:text-gray-100">
                  Deterministic Verification
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Same file → same result every time. We use only hashes and metadata; no randomness.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-4 rounded-xl bg-green-50/50 dark:bg-green-950/20 border border-green-100 dark:border-green-900/50">
              <div className="w-6 h-6 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center flex-shrink-0 mt-1">
                <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <p className="font-semibold text-gray-900 dark:text-gray-100">
                  Provenance, Not Data
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  NFTs prove your audit passed. They don&apos;t contain or expose your model weights.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-4 rounded-xl bg-red-50/30 dark:bg-red-950/20 border border-red-100 dark:border-red-900/50">
              <div className="w-6 h-6 rounded-full bg-red-100 dark:bg-red-900 flex items-center justify-center flex-shrink-0 mt-1">
                <span className="text-red-600 dark:text-red-400 text-xs font-bold">✕</span>
              </div>
              <div>
                <p className="font-semibold text-gray-900 dark:text-gray-100">
                  No Model Weights
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  We never run AI inference or reconstruct your model. Audit only.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 p-4 rounded-xl bg-red-50/30 dark:bg-red-950/20 border border-red-100 dark:border-red-900/50">
              <div className="w-6 h-6 rounded-full bg-red-100 dark:bg-red-900 flex items-center justify-center flex-shrink-0 mt-1">
                <span className="text-red-600 dark:text-red-400 text-xs font-bold">✕</span>
              </div>
              <div>
                <p className="font-semibold text-gray-900 dark:text-gray-100">
                  No Raw Data Storage
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  We process your file, produce a report, then discard it. Only commitments are kept.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Links */}
        <div className="mt-12 flex flex-wrap justify-center gap-4">
          <Link
            href="/upload"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
          >
            Start upload
            <ArrowRight className="w-4 h-4" />
          </Link>
          <span className="text-gray-400 dark:text-gray-500 self-center">|</span>
          <p className="text-sm text-gray-500 dark:text-gray-400 self-center">
            Supported: <span className="font-mono">.lm3z</span>, <span className="font-mono">.rim0</span>, <span className="font-mono">.rim95</span>
          </p>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <p className="text-center text-gray-600 dark:text-gray-400">
            Built with Next.js, Solana, and Metaplex • Devnet
          </p>
        </div>
      </footer>
    </div>
  );
}
