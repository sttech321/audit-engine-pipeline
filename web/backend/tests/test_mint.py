"""
Tests for the mint endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ─── MINT PREPARE TESTS ──────────────────────────────────────────────────────

def test_prepare_mint_valid():
    """Valid mint prepare request should succeed."""
    response = client.post("/api/mint/prepare", json={
        "uploadId": "550e8400-e29b-41d4-a716-446655440000",
        "metadata": {"name": "Test NFT", "description": "Test"},
        "walletAddress": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "fileHash": "a" * 64
    })
    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert "mintHash" in data
    assert "nftMetadata" in data


def test_prepare_mint_invalid_wallet():
    """Invalid wallet address should fail validation."""
    response = client.post("/api/mint/prepare", json={
        "uploadId": "550e8400-e29b-41d4-a716-446655440000",
        "metadata": {"name": "Test NFT"},
        "walletAddress": "invalid-wallet",
        "fileHash": "a" * 64
    })
    assert response.status_code == 422


def test_prepare_mint_invalid_file_hash():
    """Invalid file hash should fail validation."""
    response = client.post("/api/mint/prepare", json={
        "uploadId": "550e8400-e29b-41d4-a716-446655440000",
        "metadata": {"name": "Test NFT"},
        "walletAddress": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "fileHash": "tooshort"
    })
    assert response.status_code == 422


def test_prepare_mint_empty_upload_id():
    """Empty upload ID should fail validation."""
    response = client.post("/api/mint/prepare", json={
        "uploadId": "",
        "metadata": {"name": "Test NFT"},
        "walletAddress": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "fileHash": "a" * 64
    })
    assert response.status_code == 422


# ─── MINT FINALIZE TESTS ─────────────────────────────────────────────────────

def test_finalize_mint_valid():
    """Valid finalize request should succeed."""
    response = client.post("/api/mint/finalize", json={
        "mintAddress": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "uploadId": "550e8400-e29b-41d4-a716-446655440000",
        "signature": "5" * 88
    })
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_finalize_mint_invalid_address():
    """Invalid mint address should fail validation."""
    response = client.post("/api/mint/finalize", json={
        "mintAddress": "invalid",
        "uploadId": "550e8400-e29b-41d4-a716-446655440000",
        "signature": "5" * 88
    })
    assert response.status_code == 422


def test_finalize_mint_short_signature():
    """Too short signature should fail validation."""
    response = client.post("/api/mint/finalize", json={
        "mintAddress": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "uploadId": "550e8400-e29b-41d4-a716-446655440000",
        "signature": "short"
    })
    assert response.status_code == 422
