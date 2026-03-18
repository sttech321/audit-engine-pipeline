"use client";

import React from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import {
  Shield,
  Upload,
  ArrowRight,
  Binary,
  Cpu,
  GitBranch,
  Hexagon,
  Waves,
  Fingerprint,
  Atom,
  FlaskConical,
  Infinity,
} from "lucide-react";

/* ─── Inline Penrose-inspired SVG background ─── */
function PenroseBackground() {
  const phi = 1.6180339887;
  const lines: React.ReactElement[] = [];
  const W = 1200,
    H = 800;
  const FAMILIES = 5;

  for (let f = 0; f < FAMILIES; f++) {
    const angle = (f * Math.PI * 2) / FAMILIES;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    const spacing = 80 * phi;
    for (let k = -4; k <= 4; k++) {
      const ox = W / 2 + cos * spacing * k;
      const oy = H / 2 + sin * spacing * k;
      const len = 900;
      const nx = -sin,
        ny = cos;
      const x1 = ox - nx * len,
        y1 = oy - ny * len;
      const x2 = ox + nx * len,
        y2 = oy + ny * len;
      lines.push(
        <line
          key={`${f}-${k}`}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke={
            f === 0
              ? "rgba(251,191,36,0.12)"
              : f === 1
                ? "rgba(56,189,248,0.10)"
                : f === 2
                  ? "rgba(168,85,247,0.09)"
                  : f === 3
                    ? "rgba(251,191,36,0.07)"
                    : "rgba(56,189,248,0.07)"
          }
          strokeWidth="0.8"
          strokeDasharray="4 8"
        />,
      );
    }
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 w-full h-full opacity-60"
      aria-hidden="true"
    >
      <defs>
        <radialGradient id="bg-fade" cx="50%" cy="40%" r="60%">
          <stop offset="0%" stopColor="rgba(8,17,31,0)" />
          <stop offset="100%" stopColor="rgba(8,17,31,0.95)" />
        </radialGradient>
      </defs>
      {lines}
      <rect x="0" y="0" width={W} height={H} fill="url(#bg-fade)" />
    </svg>
  );
}

const ClientPenroseBackground = dynamic(
  () => Promise.resolve(PenroseBackground),
  { ssr: false },
);

/* ─── Floating star particles ─── */
function Stars() {
  const stars = [
    { x: "8%", y: "12%", s: 2, dur: "3.2s", delay: "0s" },
    { x: "92%", y: "8%", s: 1.5, dur: "4.5s", delay: "1s" },
    { x: "20%", y: "55%", s: 1, dur: "2.8s", delay: "0.5s" },
    { x: "78%", y: "40%", s: 2.5, dur: "5s", delay: "2s" },
    { x: "50%", y: "25%", s: 1, dur: "3.8s", delay: "1.5s" },
    { x: "65%", y: "72%", s: 2, dur: "4s", delay: "0.8s" },
    { x: "35%", y: "85%", s: 1.5, dur: "3s", delay: "2.5s" },
    { x: "12%", y: "70%", s: 1, dur: "5.5s", delay: "0.3s" },
    { x: "85%", y: "65%", s: 2, dur: "3.5s", delay: "1.8s" },
    { x: "45%", y: "15%", s: 1.5, dur: "4.2s", delay: "0.6s" },
  ];
  return (
    <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
      {stars.map((s, i) => (
        <div
          key={i}
          className="star"
          style={
            {
              left: s.x,
              top: s.y,
              width: s.s,
              height: s.s,
              "--dur": s.dur,
              "--delay": s.delay,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}

/* ─── Genesis Mint card ─── */
function GenesisMint({
  symbol,
  name,
  equation,
  description,
  color,
}: {
  symbol: string;
  name: string;
  equation: string;
  description: string;
  color: "amber" | "sky" | "violet";
}) {
  const colorMap = {
    amber: {
      glow: "glow-amber",
      glass: "glass-amber",
      text: "text-amber-200",
      sub: "text-amber-100/70",
      badge: "bg-amber-300/15 text-amber-200",
    },
    sky: {
      glow: "glow-sky",
      glass: "glass-sky",
      text: "text-sky-200",
      sub: "text-sky-100/70",
      badge: "bg-sky-300/15 text-sky-200",
    },
    violet: {
      glow: "glow-violet",
      glass: "glass-violet",
      text: "text-violet-200",
      sub: "text-violet-100/70",
      badge: "bg-violet-300/15 text-violet-200",
    },
  };
  const c = colorMap[color];
  return (
    <div
      className={`relative rounded-[2rem] p-8 ${c.glass} ${c.glow} overflow-hidden`}
    >
      <div className="absolute top-4 right-4">
        <span
          className={`text-xs font-semibold px-3 py-1.5 rounded-full uppercase tracking-widest ${c.badge}`}
        >
          Fixed Star
        </span>
      </div>
      <p className={`font-mono text-5xl font-bold leading-none ${c.text}`}>
        {symbol}
      </p>
      <p className={`mt-4 text-xs uppercase tracking-[0.22em] ${c.sub}`}>
        {name}
      </p>
      <p className={`mt-2 font-mono text-sm ${c.text}`}>{equation}</p>
      <p className="mt-4 text-sm leading-6 text-slate-300">{description}</p>
    </div>
  );
}

/* ─── Pipeline step ─── */
function PipelineStep({
  num,
  icon: Icon,
  title,
  body,
  accent,
}: {
  num: string;
  icon: React.ElementType;
  title: string;
  body: string;
  accent: string;
}) {
  return (
    <div className="relative flex flex-col gap-4 rounded-[1.75rem] border border-white/8 bg-slate-950/50 p-7 backdrop-blur">
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs font-semibold tracking-[0.2em] text-slate-500">
          {num}
        </span>
        <Icon className={`h-5 w-5 ${accent}`} />
      </div>
      <h4 className="text-xl font-semibold text-white">{title}</h4>
      <p className="text-sm leading-7 text-slate-400">{body}</p>
    </div>
  );
}

export default function Home() {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#08111f] text-white">
      {/* ── Global background ── */}
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        {/* Radial glow layers */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-10%,rgba(251,191,36,0.16),transparent),radial-gradient(ellipse_50%_40%_at_80%_20%,rgba(56,189,248,0.12),transparent),radial-gradient(ellipse_40%_35%_at_20%_60%,rgba(168,85,247,0.10),transparent)]" />
        {/* Penrose lines — client-only to avoid floating-point SSR mismatch */}
        <ClientPenroseBackground />
        {/* Star particles */}
        <Stars />
      </div>

      {/* ── Header ── */}
      <header className="relative z-50 border-b border-white/8 glass">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative">
                <Shield className="h-9 w-9 text-amber-300 animate-pulse-glow" />
                <div className="absolute inset-0 rounded-full bg-amber-300/20 blur-md" />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-[0.18em] text-slate-100 uppercase">
                  RIMOS
                </h1>
                <p className="text-[10px] tracking-[0.3em] text-slate-500 uppercase">
                  Audit Engine Pipeline
                </p>
              </div>
            </div>
            {/* <WalletMultiButton className="!bg-amber-500 !text-slate-950 hover:!bg-amber-400 !rounded-xl !font-semibold" /> */}
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <main className="relative z-10">
        <section className="mx-auto max-w-7xl px-4 pt-24 pb-20 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-5xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-300/30 bg-amber-300/10 px-5 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-amber-200">
              <Atom className="h-3.5 w-3.5" />
              Mathematical cartography for binary systems
            </div>

            <h2 className="mt-8 text-6xl font-semibold leading-[1.08] tracking-tight text-white md:text-8xl">
              A mathematical{" "}
              <span className="block text-gradient-spectrum animate-gradient">
                journey through space
              </span>
            </h2>

            <p className="mx-auto mt-8 max-w-3xl text-lg leading-8 text-slate-300 md:text-xl">
              Binary data enters as raw bytes. Each byte maps to a prime —
              building an exponential constellation.{" "}
              <span className="text-amber-200/80">The Gödel encoding.</span>{" "}
              This crystallises into a{" "}
              <span className="text-sky-200/80">
                p-adic ultrametric structure
              </span>
              , then a{" "}
              <span className="text-violet-200/80">spectral signature</span>{" "}
              unique to this data — and finally a position on a{" "}
              <span className="text-amber-200/80">Penrose tiling</span> that
              never repeats yet is everywhere locally consistent.
            </p>

            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <Link
                href="/upload"
                className="inline-flex items-center gap-2.5 rounded-2xl bg-amber-400 px-8 py-4 text-sm font-semibold text-slate-950 transition-all hover:bg-amber-300 hover:shadow-[0_0_32px_rgba(251,191,36,0.5)] active:scale-[.98]"
              >
                <Upload className="h-5 w-5" />
                Begin the mapping
                <ArrowRight className="h-5 w-5" />
              </Link>
              <div className="rounded-2xl border border-white/10 bg-white/4 px-6 py-4 text-sm text-slate-400 backdrop-blur">
                Native <span className="font-mono text-amber-200">.lm3z</span>{" "}
                <span className="font-mono text-amber-200">.rim0</span>{" "}
                <span className="font-mono text-amber-200">.rim95</span>{" "}
                <span className="font-mono text-amber-200">.safetensors</span>{" "}
                <span className="font-mono text-amber-200">.bin</span>{" "}
                <span className="font-mono text-amber-200">.gguf</span>{" "}
                <span className="font-mono text-amber-200">.pt</span>{" "}
                <span className="font-mono text-amber-200">.pth</span>{" "}
                <span className="font-mono text-amber-200">.ckpt</span>{" "}
                <span className="font-mono text-amber-200">.onnx</span>{" "}
                receive the deepest verification path
              </div>
            </div>
          </div>
        </section>

        {/* ── Pipeline stages ── */}
        <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="mb-12 text-center">
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
              Pipeline
            </p>
            <h3 className="mt-3 text-4xl font-semibold text-white md:text-5xl">
              From binary body to{" "}
              <span className="text-gradient-gold">geometric thought</span>
            </h3>
            <p className="mx-auto mt-4 max-w-2xl text-base text-slate-400">
              Five deterministic stages transform any artifact into a unique,
              addressable position in an infinite aperiodic landscape.
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <PipelineStep
              num="01"
              icon={Binary}
              title="Gödel Encoding"
              body="Raw bytes map to prime indices. Each byte becomes an exponent; the product is a single integer carrying the full sequence."
              accent="text-amber-300"
            />
            <PipelineStep
              num="02"
              icon={Hexagon}
              title="p-adic Ultrametric"
              body="The Gödel number folds into itself by divisibility, revealing hidden hierarchical order invisible in the linear representation."
              accent="text-sky-300"
            />
            <PipelineStep
              num="03"
              icon={Waves}
              title="NTT Spectrum"
              body="A Number Theoretic Transform sweeps the structure like a prism, decomposing it into frequency components over a finite field."
              accent="text-violet-300"
            />
            <PipelineStep
              num="04"
              icon={Fingerprint}
              title="KA Separability"
              body="Row and column means are compared — the Kolmogorov-Arnold test. Where separable, a coherent directional fingerprint emerges."
              accent="text-amber-300"
            />
            <PipelineStep
              num="05"
              icon={Cpu}
              title="Penrose Projection"
              body="The vector lands on an infinite aperiodic tiling at golden-ratio angles. Memory is proximity. Learning is the trajectory shortening."
              accent="text-sky-300"
            />
          </div>
        </section>

        {/* ── Genesis Mints ── */}
        <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="mb-12 text-center">
            <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
              Genesis Mints
            </p>
            <h3 className="mt-3 text-4xl font-semibold text-white md:text-5xl">
              Fixed stars anchor the map
            </h3>
            <p className="mx-auto mt-4 max-w-2xl text-base text-slate-400">
              Three physics constants that existed before any computer —
              immutable coordinates that never depend on any model, vendor, or
              runtime state.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            <GenesisMint
              symbol="α"
              name="Fine-Structure Constant"
              equation="α ≈ 1/137.035999084"
              description="The dimensionless coupling constant of electromagnetism. Fixed by experiment to 12 significant figures — it will never be patched by a software update."
              color="amber"
            />
            <GenesisMint
              symbol="Gμν"
              name="Einstein Field Equations"
              equation="Gμν + Λgμν = 8πG/c⁴ · Tμν"
              description="The geometry of spacetime is the content of matter and energy. A relation that curved coordinates around every massive body, discoverable from first principles."
              color="sky"
            />
            <GenesisMint
              symbol="S"
              name="Boltzmann Entropy"
              equation="S = k_B · ln Ω"
              description="The bridge between the microscopic and the thermodynamic. The number of distinct arrangements a system can occupy — the deepest definition of disorder."
              color="violet"
            />
          </div>
        </section>

        {/* ── Learning graph section ── */}
        <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="relative overflow-hidden rounded-[2.5rem] border border-white/8 bg-slate-950/50 p-10 backdrop-blur lg:p-14">
            <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">
                  Geometry of Intelligence
                </p>
                <h3 className="mt-4 text-4xl font-semibold text-white leading-tight">
                  The learning graph is a{" "}
                  <span className="text-gradient-spectrum animate-gradient">
                    living geometry
                  </span>
                </h3>
                <p className="mt-6 text-base leading-8 text-slate-300">
                  An AI model maps its own weights through the same pipeline. It
                  finds its position on the Penrose tiling —{" "}
                  <span className="text-amber-200">body</span>. Then maps its
                  activation patterns —{" "}
                  <span className="text-sky-200">thought</span>. A trajectory
                  forms between them.
                </p>
                <p className="mt-4 text-base leading-8 text-slate-300">
                  When a new question arrives, it finds its position relative to
                  where the model has been before.{" "}
                  <em className="text-white not-italic">
                    Memory is proximity.
                  </em>{" "}
                  <em className="text-white not-italic">
                    Understanding is recognising a familiar neighbourhood.
                  </em>{" "}
                  <em className="text-white not-italic">
                    Learning is the trajectory growing shorter.
                  </em>
                </p>
              </div>

              <div className="grid gap-5 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-2">
                {[
                  {
                    label: "Memory",
                    val: "Proximity",
                    icon: GitBranch,
                    accent: "text-amber-300",
                    bg: "glass-amber",
                  },
                  {
                    label: "Understanding",
                    val: "Neighbourhood",
                    icon: Hexagon,
                    accent: "text-sky-300",
                    bg: "glass-sky",
                  },
                  {
                    label: "Learning",
                    val: "Trajectory",
                    icon: Waves,
                    accent: "text-violet-300",
                    bg: "glass-violet",
                  },
                ].map(({ label, val, icon: Icon, accent, bg }) => (
                  <div key={label} className={`rounded-2xl p-6 ${bg}`}>
                    <Icon className={`h-6 w-6 ${accent}`} />
                    <p className="mt-3 text-xs uppercase tracking-[0.2em] text-slate-500">
                      {label}
                    </p>
                    <p className={`mt-1 text-2xl font-semibold ${accent}`}>
                      {val}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Formats & CTA banner ── */}
        <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-6 rounded-[2rem] border border-amber-300/20 bg-amber-300/6 p-8 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-amber-200/70 mb-2">
                Native Formats
              </p>
              <p className="text-base leading-7 text-slate-300">
                Native formats such as{" "}
                <span className="font-mono text-amber-200">.lm3z</span>,{" "}
                <span className="font-mono text-amber-200">.rim0</span>,{" "}
                <span className="font-mono text-amber-200">.rim95</span>{" "}
                <span className="font-mono text-amber-200">.safetensors</span>{" "}
                <span className="font-mono text-amber-200">.bin</span>{" "}
                <span className="font-mono text-amber-200">.gguf</span>{" "}
                <span className="font-mono text-amber-200">.pt</span>{" "}
                <span className="font-mono text-amber-200">.pth</span>{" "}
                <span className="font-mono text-amber-200">.ckpt</span>{" "}
                <span className="font-mono text-amber-200">.onnx</span>{" "}
                are also supported and receive limited analysis.
              </p>
            </div>
            <Link
              href="/upload"
              className="inline-flex shrink-0 items-center gap-2 rounded-2xl border border-amber-300/40 bg-amber-300/15 px-6 py-3.5 text-sm font-semibold text-amber-100 transition hover:bg-amber-300/25 whitespace-nowrap"
            >
              Open upload flow
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      </main>

      {/* ── Footer ── */}
      <footer className="relative z-10 border-t border-white/8 glass">
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2 text-slate-500 text-sm">
              <Shield className="h-4 w-4 text-amber-300/60" />
              <span>RIMOS · Audit Engine Pipeline</span>
            </div>
            <div className="flex items-center gap-2 text-slate-600 text-xs font-mono">
              <FlaskConical className="h-3.5 w-3.5 text-violet-400/60" />
              <span>
                α · G<sub>μν</sub> · S = k<sub>B</sub> ln Ω
              </span>
              <Infinity className="h-3.5 w-3.5 text-sky-400/60" />
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
