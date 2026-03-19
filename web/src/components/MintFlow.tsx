"use client";

import { FC, useCallback, useEffect, useMemo, useState } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { irysStorage, Metaplex, walletAdapterIdentity } from "@metaplex-foundation/js";
import { CheckCircle, Coins, ExternalLink, Loader2 } from "lucide-react";
import axios from "axios";
import type {
  ExtendedAuditResult,
  IpfsUploadResponse,
  KPI,
  MintPrepareResponse,
  UploadResponse,
} from "@shared/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MIN_SOL_FOR_MINT = 0.01;
const MAX_NFT_NAME_LENGTH = 32;

const sanitizeNftName = (rawName: string, uploadId: string): string => {
  const fallback = `RIMOS #${uploadId.slice(0, 8)}`;
  const value = (rawName || "").trim() || fallback;
  return value.slice(0, MAX_NFT_NAME_LENGTH);
};

interface MintFlowProps {
  uploadData: UploadResponse;
}

interface MintResult {
  mintAddress: string;
  metadataUri: string;
  mintHash: string;
  txSignature: string;
  explorerMintUrl: string;
  explorerTxUrl: string;
}

const findKpiValue = (kpis: KPI[], label: string): number | null => {
  const kpi = kpis.find((item) => item.label.toLowerCase() === label.toLowerCase());
  if (!kpi) return null;
  if (typeof kpi.value === "number") return kpi.value;
  const parsed = Number(kpi.value);
  return Number.isFinite(parsed) ? parsed : null;
};

const mapMintError = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    const apiError = error.response?.data?.error;
    if (typeof detail === "string") return detail;
    if (typeof apiError === "string") return apiError;
  }

  const message = error instanceof Error ? error.message : "Unknown minting error";
  const lower = message.toLowerCase();
  if (lower.includes("walletnotconnected") || lower.includes("connect your wallet")) {
    return "Wallet not connected. Connect Phantom and retry.";
  }
  if (lower.includes("user rejected") || lower.includes("rejected the request")) {
    return "Transaction was rejected in wallet approval.";
  }
  if (
    lower.includes("insufficient funds") ||
    lower.includes("insufficient lamports") ||
    lower.includes("0x1")
  ) {
    return "Insufficient SOL on devnet wallet. Add devnet SOL and retry.";
  }
  if (lower.includes("rpc") || lower.includes("blockhash") || lower.includes("node is behind")) {
    return "Solana RPC is temporarily unavailable. Please retry in a moment.";
  }
  if (lower.includes("name too long")) {
    return "NFT name exceeds Solana's 32 character limit. Please retry.";
  }
  return message;
};

export const MintFlow: FC<MintFlowProps> = ({ uploadData }) => {
  const { connection } = useConnection();
  const { publicKey, signTransaction, signAllTransactions } = useWallet();
  const [isMinting, setIsMinting] = useState(false);
  const [mintResult, setMintResult] = useState<MintResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ipfsWarning, setIpfsWarning] = useState<string | null>(null);
  const [solBalance, setSolBalance] = useState<number | null>(null);
  const [isCheckingBalance, setIsCheckingBalance] = useState(false);

  const isAuditFailed = useMemo(() => {
    const status = uploadData.verification.status.toLowerCase();
    return status.includes("failed") || status.includes("rejected");
  }, [uploadData.verification.status]);

  const isLowBalance = useMemo(() => {
    if (solBalance === null) return false;
    return solBalance < MIN_SOL_FOR_MINT;
  }, [solBalance]);

  const refreshBalance = useCallback(async () => {
    if (!publicKey) {
      setSolBalance(null);
      return;
    }
    setIsCheckingBalance(true);
    try {
      const lamports = await connection.getBalance(publicKey, "confirmed");
      setSolBalance(lamports / 1_000_000_000);
    } catch {
      setSolBalance(null);
    } finally {
      setIsCheckingBalance(false);
    }
  }, [connection, publicKey]);

  const mintStatus = useMemo(() => {
    if (mintResult) return "Certificate minted successfully.";
    if (isMinting) return "Minting certificate on Solana...";
    if (error) return "Minting failed, but your audit report remains unaffected.";
    return null;
  }, [mintResult, isMinting, error]);

  const handleMint = async () => {
    if (!publicKey || !signTransaction) {
      setError("Wallet not connected. Connect Phantom and retry.");
      return;
    }
    if (isLowBalance) {
      setError("Transaction cannot proceed due to insufficient SOL. Please add funds and try again.");
      return;
    }

    setIsMinting(true);
    setError(null);
    setIpfsWarning(null);

    try {
      let extendedReport: ExtendedAuditResult | null = null;
      try {
        const reportResponse = await axios.get<ExtendedAuditResult>(
          `${API_URL}/api/report/${uploadData.uploadId}/extended`,
        );
        extendedReport = reportResponse.data;
      } catch {
        extendedReport = null;
      }

      const integrityScore =
        extendedReport ? findKpiValue(extendedReport.kpis, "Audit Score") : findKpiValue(uploadData.kpis, "Audit Score");
      const riskLevel = extendedReport?.risk_badge?.label || "Unknown";
      const reportReference =
        typeof window !== "undefined"
          ? `${window.location.origin}/report/${uploadData.uploadId}`
          : `/report/${uploadData.uploadId}`;
      const nftName = sanitizeNftName(
        uploadData.metadata?.name || `RIMOS Certificate #${uploadData.uploadId.slice(0, 8)}`,
        uploadData.uploadId,
      );

      const preparedMetadata = {
        name: nftName,
        description:
          uploadData.metadata?.description ||
          `Full audit report for artifact ${uploadData.uploadId} with integrity score ${
            integrityScore ?? "N/A"
          } and risk classification ${riskLevel}.`,
        attributes: [
          { trait_type: "Integrity Score", value: integrityScore ?? "N/A" },
          { trait_type: "Risk Level", value: riskLevel },
          { trait_type: "Artifact Hash", value: uploadData.fileHash },
          { trait_type: "Report Reference", value: reportReference },
        ],
      };

      const ipfsResponse = await axios.post<IpfsUploadResponse>(`${API_URL}/api/ipfs/upload`, {
        uploadId: uploadData.uploadId,
        metadata: preparedMetadata,
        fileHash: uploadData.fileHash,
        auditData: {
          integrityScore,
          riskLevel,
          verificationStatus: uploadData.verification.status,
          artifactHash: uploadData.fileHash,
          reportReference,
        },
      });

      if (ipfsResponse.data.fallbackUsed) {
        setIpfsWarning(
          "Metadata upload failed. A temporary fallback is being used.\n\nNote: This NFT may not include permanent metadata storage.",
        );
      }

      const prepareResponse = await axios.post<MintPrepareResponse>(`${API_URL}/api/mint/prepare`, {
        uploadId: uploadData.uploadId,
        metadata: {
          ...preparedMetadata,
          symbol: "RIMOS",
        },
        walletAddress: publicKey.toString(),
        fileHash: uploadData.fileHash,
        metadataUrl: ipfsResponse.data.url,
        auditData: {
          integrityScore,
          riskLevel,
          verificationStatus: uploadData.verification.status,
          artifactHash: uploadData.fileHash,
          reportReference,
        },
      });

      const metaplex = Metaplex.make(connection)
        .use(walletAdapterIdentity({ publicKey, signTransaction, signAllTransactions }))
        .use(irysStorage());
      const mintName = sanitizeNftName(prepareResponse.data.nftMetadata.name, uploadData.uploadId);
      if (mintName.length > MAX_NFT_NAME_LENGTH) {
        throw new Error("NFT name exceeds 32 character limit");
      }

      const created = await metaplex.nfts().create({
        uri: prepareResponse.data.metadata.url,
        name: mintName,
        symbol: prepareResponse.data.nftMetadata.symbol,
        sellerFeeBasisPoints: 0,
      });

      const txSignature = created.response.signature;
      if (!txSignature) {
        throw new Error("Missing on-chain transaction signature from wallet flow.");
      }

      await axios.post(`${API_URL}/api/mint/finalize`, {
        mintAddress: created.nft.address.toString(),
        uploadId: uploadData.uploadId,
        signature: txSignature,
      });

      setMintResult({
        mintAddress: created.nft.address.toString(),
        metadataUri: prepareResponse.data.metadata.url,
        mintHash: prepareResponse.data.mintHash,
        txSignature,
        explorerMintUrl: `https://explorer.solana.com/address/${created.nft.address.toString()}?cluster=devnet`,
        explorerTxUrl: `https://explorer.solana.com/tx/${txSignature}?cluster=devnet`,
      });
    } catch (mintError: unknown) {
      const mapped = mapMintError(mintError);
      if (
        mapped.toLowerCase().includes("insufficient sol") ||
        mapped.toLowerCase().includes("insufficient funds")
      ) {
        setError("Transaction cannot proceed due to insufficient SOL. Please add funds and try again.");
      } else {
        setError(`${mapped} Minting failed, but your audit report is unaffected`);
      }
      console.error("Mint error:", mintError);
    } finally {
      setIsMinting(false);
    }
  };

  useEffect(() => {
    void refreshBalance();
  }, [refreshBalance]);

  const canMint = Boolean(publicKey) && !isMinting && !isAuditFailed && !isLowBalance && !mintResult;
  const buttonClass = mintResult
    ? "bg-emerald-600"
    : isLowBalance
      ? "bg-amber-600"
      : "bg-gradient-to-r from-sky-600 to-blue-600 hover:from-sky-500 hover:to-blue-500";
  const buttonLabel = mintResult
    ? "Mint Complete"
    : isMinting
      ? "Minting certificate on Solana..."
      : !publicKey
        ? "Connect wallet to mint"
        : isLowBalance
          ? "Low SOL Balance"
          : "Mint Certificate (Optional)";

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-blue-400/25 bg-blue-500/10 p-4">
        <p className="text-sm text-blue-100">
          Minting is optional and isolated from the core audit flow. Your report remains available even if minting fails.
        </p>
      </div>

      {isAuditFailed && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          The current audit status indicates failure/rejection. Minting is disabled for this artifact.
        </div>
      )}

      {!publicKey && (
        <div className="py-2">
          <WalletMultiButton className="!bg-blue-600 hover:!bg-blue-700" />
        </div>
      )}

      {publicKey && (
        <div className="rounded-xl border border-white/10 bg-slate-950/50 p-4 space-y-3">
          <p className="text-xs uppercase tracking-[0.16em] text-slate-500">Wallet</p>
          <p className="mt-2 font-mono text-sm text-slate-200">
            {publicKey.toString().slice(0, 8)}...{publicKey.toString().slice(-8)}
          </p>
          <div className="rounded-lg border border-slate-700/60 bg-slate-900/60 p-3">
            <p className="break-all font-mono text-xs text-slate-300">{publicKey.toString()}</p>
            <button
              type="button"
              onClick={() => navigator.clipboard.writeText(publicKey.toString())}
              className="mt-2 rounded-md border border-slate-600 px-2 py-1 text-xs text-slate-300 hover:border-slate-400"
            >
              Copy full address
            </button>
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-slate-300">
              SOL balance:{" "}
              {isCheckingBalance ? "Checking..." : solBalance === null ? "Unavailable" : `${solBalance.toFixed(4)} SOL`}
            </p>
            <button
              type="button"
              onClick={refreshBalance}
              disabled={isCheckingBalance || isMinting}
              className="rounded-md border border-slate-600 px-3 py-1 text-xs text-slate-300 hover:border-slate-400 disabled:opacity-60"
            >
              Refresh
            </button>
          </div>
          {isLowBalance && (
            <div className="rounded-lg border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-100">
              <p>Insufficient SOL balance to complete minting.</p>
              <p className="mt-2">
                For testing, switch to Devnet and request free SOL from:{" "}
                <a
                  href="https://faucet.solana.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline text-amber-200 hover:text-amber-100"
                >
                  https://faucet.solana.com
                </a>
              </p>
            </div>
          )}
        </div>
      )}

      <button
        onClick={handleMint}
        disabled={!canMint}
        className={`w-full inline-flex items-center justify-center gap-2 rounded-xl px-6 py-3 font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60 ${buttonClass}`}
      >
        {isMinting ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            {buttonLabel}
          </>
        ) : (
          <>
            <Coins className="h-4 w-4" />
            {buttonLabel}
          </>
        )}
      </button>

      {mintStatus && (
        <div
          className={`rounded-xl p-3 text-sm ${
            mintResult
              ? "border border-emerald-400/35 bg-emerald-500/10 text-emerald-100"
              : error
                ? "border border-red-500/30 bg-red-500/10 text-red-200"
                : "border border-sky-400/30 bg-sky-500/10 text-sky-100"
          }`}
        >
          {mintStatus}
        </div>
      )}

      {ipfsWarning && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-sm text-amber-200">
          {ipfsWarning}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {mintResult && (
        <div className="space-y-4 rounded-xl border border-emerald-400/35 bg-emerald-500/10 p-5">
          <div className="flex items-start gap-3">
            <CheckCircle className="mt-0.5 h-5 w-5 text-emerald-300" />
            <div>
              <h4 className="font-semibold text-emerald-200">Certificate minted successfully</h4>
              <p className="mt-1 text-sm text-emerald-100">Minting complete on Solana devnet.</p>
            </div>
          </div>
          <div className="space-y-2 text-sm">
            <div>
              <p className="text-slate-400">Mint address</p>
              <p className="break-all font-mono text-emerald-100">{mintResult.mintAddress}</p>
            </div>
            <div>
              <p className="text-slate-400">Transaction signature</p>
              <p className="break-all font-mono text-emerald-100">{mintResult.txSignature}</p>
            </div>
            <div>
              <p className="text-slate-400">Mint hash</p>
              <p className="break-all font-mono text-emerald-100">{mintResult.mintHash}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <a
              href={mintResult.explorerMintUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-sky-400/40 bg-sky-500/10 px-4 py-2 text-sm font-medium text-sky-200 transition hover:bg-sky-500/20"
            >
              View mint
              <ExternalLink className="h-4 w-4" />
            </a>
            <a
              href={mintResult.explorerTxUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-sky-400/40 bg-sky-500/10 px-4 py-2 text-sm font-medium text-sky-200 transition hover:bg-sky-500/20"
            >
              View transaction
              <ExternalLink className="h-4 w-4" />
            </a>
            <a
              href={mintResult.metadataUri}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 rounded-lg border border-violet-400/40 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20"
            >
              View metadata
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>
      )}
    </div>
  );
};
