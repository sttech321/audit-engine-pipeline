"use client";

import type { ArtifactBlock } from "@shared/types";

type BlockchainInfoProps = {
  block?: ArtifactBlock | null;
  chainHeight?: number;
};

const HashField = ({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) => {
  if (!value) return null;

  return (
    <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5 md:col-span-2">
      <div className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-500">
        {label}
      </div>
      <p className="break-all rounded-xl border border-amber-300/15 bg-amber-300/5 p-3 font-mono text-xs leading-6 text-amber-200/70">
        {value}
      </p>
    </div>
  );
};

export default function BlockchainInfo({
  block,
  chainHeight,
}: BlockchainInfoProps) {
  if (!block) return null;

  return (
    <section className="rounded-[2rem] border border-white/8 bg-slate-950/60 p-8 backdrop-blur shadow-xl shadow-black/30">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white">Blockchain Record</h2>
        <p className="mt-1.5 text-sm text-slate-400">
          This artifact position was written to the internal blockchain as a
          persistent chain record.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
          <div className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-500">
            Block Index
          </div>
          <p className="text-2xl font-semibold text-sky-300">
            {typeof block.index === "number" ? block.index : "Not available"}
          </p>
        </div>

        <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5">
          <div className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-500">
            Chain Height
          </div>
          <p className="text-2xl font-semibold text-sky-300">
            {typeof chainHeight === "number" ? chainHeight : "Not available"}
          </p>
        </div>

        <div className="rounded-2xl border border-white/8 bg-slate-900/60 p-5 md:col-span-2">
          <div className="mb-3 text-xs uppercase tracking-[0.2em] text-slate-500">
            Timestamp
          </div>
          <p className="text-sm font-medium text-slate-300">
            {block.timestamp || "Not available"}
          </p>
        </div>

        <HashField label="Artifact Hash" value={block.artifact_hash} />
        <HashField label="Block Hash" value={block.block_hash} />
        <HashField label="Previous Block Hash" value={block.prev_block_hash} />
      </div>
    </section>
  );
}
