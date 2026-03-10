'use client';

import { FC, useState } from 'react';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import { WalletMultiButton } from '@solana/wallet-adapter-react-ui';
import { Metaplex, walletAdapterIdentity, irysStorage } from '@metaplex-foundation/js';
import { Loader2, CheckCircle, ExternalLink, Coins } from 'lucide-react';
import axios from 'axios';
import type { UploadResponse, MintPrepareResponse } from '@shared/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface MintFlowProps {
    uploadData: UploadResponse;
}

export const MintFlow: FC<MintFlowProps> = ({ uploadData }) => {
    const { publicKey, signTransaction } = useWallet();
    const { connection } = useConnection();
    const [isMinting, setIsMinting] = useState(false);
    const [mintResult, setMintResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    const handleMint = async () => {
        if (!publicKey || !signTransaction) {
            setError('Please connect your wallet first');
            return;
        }

        setIsMinting(true);
        setError(null);

        try {
            // Step 1: Prepare metadata and upload to IPFS
            const prepareResponse = await axios.post<MintPrepareResponse>(
                `${API_URL}/api/mint/prepare`,
                {
                    uploadId: uploadData.uploadId,
                    metadata: uploadData.metadata,
                    walletAddress: publicKey.toString(),
                    fileHash: uploadData.fileHash
                }
            );

            const { metadata, mintHash, nftMetadata } = prepareResponse.data;

            // Step 2: Initialize Metaplex
            const metaplex = Metaplex.make(connection)
                .use(walletAdapterIdentity({ publicKey, signTransaction }))
                .use(irysStorage());

            // Step 3: Create NFT
            const { nft } = await metaplex.nfts().create({
                uri: metadata.url,
                name: nftMetadata.name,
                sellerFeeBasisPoints: 0,
                symbol: nftMetadata.symbol,
            });

            // Step 4: Record mint
            await axios.post(`${API_URL}/api/mint/finalize`, {
                mintAddress: nft.address.toString(),
                uploadId: uploadData.uploadId,
                signature: 'completed'
            });

            setMintResult({
                mintAddress: nft.address.toString(),
                metadataUri: metadata.url,
                mintHash,
                explorerUrl: `https://explorer.solana.com/address/${nft.address.toString()}?cluster=devnet`
            });

        } catch (err: any) {
            setError(err.response?.data?.error || err.message || 'Failed to mint NFT');
            console.error('Mint error:', err);
        } finally {
            setIsMinting(false);
        }
    };

    const isAuditFailed = uploadData.verification.status.toLowerCase().includes('failed') ||
        uploadData.verification.status.toLowerCase().includes('rejected');

    return (
        <div className="space-y-6">
            {/* <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-1">
                        Mint Audit NFT
                    </h2>
                    <span className="inline-block text-xs font-semibold bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 px-2 py-0.5 rounded-full">
                        ⚗️ Alpha / Internal Tool — Not a Certification
                    </span>
                </div>
            </div> */}

            {/* Block minting for failed audits */}
            {isAuditFailed && (
                <div className="p-5 bg-red-50 dark:bg-red-950/20 border-2 border-red-200 dark:border-red-800 rounded-xl">
                    <p className="text-sm font-semibold text-red-800 dark:text-red-200">
                        {/* ❌ Minting is disabled — Audit Verification Failed */}
                    </p>
                    <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                        The uploaded artifact did not pass the cryptographic pipeline checks.
                        Re-upload a valid audit artifact to proceed.
                    </p>
                </div>
            )}

            {!publicKey ? (
                <div className="text-center py-8">
                    {/* <p className="text-gray-600 dark:text-gray-400 mb-4">
                        Connect your wallet to mint an NFT
                    </p> */}
                    {!isAuditFailed && <WalletMultiButton className="!bg-blue-600 hover:!bg-blue-700" />}
                </div>
            ) : mintResult ? (
                <div className="space-y-4">
                    <div className="p-6 bg-green-50 dark:bg-green-950/20 border-2 border-green-200 dark:border-green-800 rounded-xl">
                        <div className="flex items-start gap-4">
                            <CheckCircle className="w-8 h-8 text-green-600 flex-shrink-0" />
                            <div className="flex-1">
                                <h3 className="text-lg font-semibold text-green-900 dark:text-green-100 mb-2">
                                    NFT Minted Successfully!
                                </h3>
                                <div className="space-y-2 text-sm">
                                    <div>
                                        <span className="text-gray-600 dark:text-gray-400">Mint Address:</span>
                                        <p className="font-mono text-green-700 dark:text-green-400 break-all">
                                            {mintResult.mintAddress}
                                        </p>
                                    </div>
                                    <div>
                                        <span className="text-gray-600 dark:text-gray-400">Mint Hash:</span>
                                        <p className="font-mono text-green-700 dark:text-green-400 break-all">
                                            {mintResult.mintHash}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <a
                            href={mintResult.explorerUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                        >
                            View on Solana Explorer
                            <ExternalLink className="w-4 h-4" />
                        </a>
                        <a
                            href={mintResult.metadataUri}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
                        >
                            View Metadata on IPFS
                            <ExternalLink className="w-4 h-4" />
                        </a>
                    </div>
                </div>
            ) : (
                <div className="space-y-4">
                    <div className="p-4 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg">
                        <p className="text-sm text-blue-700 dark:text-blue-400">
                            <strong>Note:</strong> Minting will upload your audit file and metadata to IPFS,
                            then create an NFT on Solana Devnet. This may take a few moments.
                        </p>
                    </div>

                    <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900 rounded-lg">
                        <div>
                            <p className="font-semibold text-gray-900 dark:text-gray-100">Connected Wallet</p>
                            <p className="text-sm font-mono text-gray-600 dark:text-gray-400">
                                {publicKey.toString().slice(0, 8)}...{publicKey.toString().slice(-8)}
                            </p>
                        </div>
                        <WalletMultiButton className="!bg-gray-600 hover:!bg-gray-700" />
                    </div>

                    <button
                        onClick={handleMint}
                        disabled={isMinting || isAuditFailed}
                        className="w-full flex items-center justify-center gap-3 px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isMinting ? (
                            <>
                                <Loader2 className="w-5 h-5 animate-spin" />
                                Minting NFT...
                            </>
                        ) : (
                            <>
                                <Coins className="w-5 h-5" />
                                Mint Audit NFT
                            </>
                        )}
                    </button>

                    {error && (
                        <div className="p-4 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg">
                            <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
