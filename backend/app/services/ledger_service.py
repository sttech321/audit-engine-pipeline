"""
Ledger chaining service for PASS97 audit provenance.

PASS97 Spec Compliant:
- ledger_prev / ledger_next formulas for chain continuity
- audit_content_sha256 canonical hash
- Deterministic chain linking

Provides cryptographic chaining between consecutive audit records.
"""
import hashlib
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from threading import Lock

from app.logging_config import logger


# ─── Ledger Entry Schema ─────────────────────────────────────────────────────

@dataclass
class LedgerEntry:
    """A single entry in the audit ledger chain."""
    
    # Core identifiers
    ledger_id: str              # Unique ledger entry ID
    sequence_number: int        # Sequential order in chain
    timestamp: float            # Unix timestamp
    
    # Content hashes
    audit_content_sha256: str   # Canonical SHA-256 of audit content
    file_hash: str              # Original file hash
    penrose_hash: str           # Penrose P3 fingerprint
    
    # Chain links
    ledger_prev: Optional[str]  # Hash link to previous entry (None for genesis)
    ledger_next: Optional[str]  # Hash link to next entry (set when next added)
    
    # Entry hash (self-referential integrity)
    entry_hash: str             # SHA-256 of this entry's contents
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "ledger_id": self.ledger_id,
            "sequence_number": self.sequence_number,
            "timestamp": self.timestamp,
            "audit_content_sha256": self.audit_content_sha256,
            "file_hash": self.file_hash,
            "penrose_hash": self.penrose_hash,
            "ledger_prev": self.ledger_prev,
            "ledger_next": self.ledger_next,
            "entry_hash": self.entry_hash
        }


# ─── Ledger Chain Functions ──────────────────────────────────────────────────

def compute_audit_content_sha256(
    file_hash: str,
    godel_fingerprint: int,
    ntt_fold: int,
    kag_score: float,
    penrose_hash: str,
    tile_hash: str
) -> str:
    """
    Compute the canonical audit_content_sha256 hash.
    
    PASS97 Spec: Combines all audit stage outputs into a single
    deterministic hash that represents the complete audit result.
    
    Args:
        file_hash: SHA-256 of original file
        godel_fingerprint: Stage 1 Gödel value
        ntt_fold: Stage 3 NTT folded checksum
        kag_score: Stage 4 KAG separability score
        penrose_hash: Stage 5 Penrose hash
        tile_hash: Stage 5 tile coordinate hash
        
    Returns:
        64-character hex string (SHA-256)
    """
    # Canonical concatenation order (deterministic)
    content = f"{file_hash}:{godel_fingerprint}:{ntt_fold}:{kag_score}:{penrose_hash}:{tile_hash}"
    return hashlib.sha256(content.encode()).hexdigest()


def compute_ledger_prev(
    previous_entry_hash: str,
    previous_audit_content: str,
    previous_sequence: int
) -> str:
    """
    Compute ledger_prev hash linking to previous entry.
    
    PASS97 Spec Formula:
    ledger_prev = SHA256(prev_entry_hash || prev_audit_content || prev_seq)
    
    Args:
        previous_entry_hash: Entry hash of previous ledger entry
        previous_audit_content: audit_content_sha256 of previous entry
        previous_sequence: Sequence number of previous entry
        
    Returns:
        64-character hex string
    """
    link_input = f"{previous_entry_hash}:{previous_audit_content}:{previous_sequence}"
    return hashlib.sha256(link_input.encode()).hexdigest()


def compute_ledger_next(
    current_entry_hash: str,
    next_audit_content: str,
    next_sequence: int
) -> str:
    """
    Compute ledger_next hash linking to next entry.
    
    PASS97 Spec Formula:
    ledger_next = SHA256(current_entry_hash || next_audit_content || next_seq)
    
    This is set on the current entry when the next entry is created.
    
    Args:
        current_entry_hash: Entry hash of current ledger entry
        next_audit_content: audit_content_sha256 of upcoming entry
        next_sequence: Sequence number of upcoming entry
        
    Returns:
        64-character hex string
    """
    link_input = f"{current_entry_hash}:{next_audit_content}:{next_sequence}"
    return hashlib.sha256(link_input.encode()).hexdigest()


def compute_entry_hash(
    ledger_id: str,
    sequence_number: int,
    timestamp: float,
    audit_content_sha256: str,
    file_hash: str,
    penrose_hash: str,
    ledger_prev: Optional[str]
) -> str:
    """
    Compute the entry_hash for a ledger entry.
    
    The entry_hash provides self-referential integrity - any modification
    to the entry will change this hash.
    
    Args:
        All fields that make up the entry (except ledger_next which is mutable)
        
    Returns:
        64-character hex string
    """
    content = (
        f"{ledger_id}:{sequence_number}:{timestamp}:"
        f"{audit_content_sha256}:{file_hash}:{penrose_hash}:"
        f"{ledger_prev or 'GENESIS'}"
    )
    return hashlib.sha256(content.encode()).hexdigest()


# ─── Ledger Chain Manager ────────────────────────────────────────────────────

class LedgerChain:
    """
    Thread-safe ledger chain manager.
    
    Maintains an ordered chain of audit entries with cryptographic linking.
    In production, this would be persisted to a database.
    """
    
    def __init__(self):
        self._entries: List[LedgerEntry] = []
        self._lock = Lock()
        self._id_counter = 0
    
    def _generate_ledger_id(self) -> str:
        """Generate a unique ledger ID."""
        self._id_counter += 1
        timestamp_part = hex(int(time.time() * 1000))[2:]
        return f"LEDGER-{timestamp_part}-{self._id_counter:06d}"
    
    def add_entry(
        self,
        audit_content_sha256: str,
        file_hash: str,
        penrose_hash: str
    ) -> LedgerEntry:
        """
        Add a new entry to the ledger chain.
        
        Args:
            audit_content_sha256: Canonical audit content hash
            file_hash: Original file SHA-256
            penrose_hash: Penrose P3 fingerprint
            
        Returns:
            The newly created LedgerEntry
        """
        with self._lock:
            ledger_id = self._generate_ledger_id()
            sequence = len(self._entries)
            timestamp = time.time()
            
            # Compute ledger_prev from previous entry
            if self._entries:
                prev_entry = self._entries[-1]
                ledger_prev = compute_ledger_prev(
                    prev_entry.entry_hash,
                    prev_entry.audit_content_sha256,
                    prev_entry.sequence_number
                )
            else:
                ledger_prev = None  # Genesis entry
            
            # Compute entry hash
            entry_hash = compute_entry_hash(
                ledger_id,
                sequence,
                timestamp,
                audit_content_sha256,
                file_hash,
                penrose_hash,
                ledger_prev
            )
            
            # Create new entry
            new_entry = LedgerEntry(
                ledger_id=ledger_id,
                sequence_number=sequence,
                timestamp=timestamp,
                audit_content_sha256=audit_content_sha256,
                file_hash=file_hash,
                penrose_hash=penrose_hash,
                ledger_prev=ledger_prev,
                ledger_next=None,  # Set when next entry added
                entry_hash=entry_hash
            )
            
            # Update previous entry's ledger_next
            if self._entries:
                prev_entry = self._entries[-1]
                prev_entry.ledger_next = compute_ledger_next(
                    prev_entry.entry_hash,
                    audit_content_sha256,
                    sequence
                )
            
            self._entries.append(new_entry)
            logger.info(f"Ledger entry added: {ledger_id} (seq={sequence})")
            
            return new_entry
    
    def get_entry(self, sequence: int) -> Optional[LedgerEntry]:
        """Get entry by sequence number."""
        with self._lock:
            if 0 <= sequence < len(self._entries):
                return self._entries[sequence]
            return None
    
    def get_latest(self) -> Optional[LedgerEntry]:
        """Get the most recent entry."""
        with self._lock:
            return self._entries[-1] if self._entries else None
    
    def verify_chain_integrity(self) -> bool:
        """
        Verify the integrity of the entire ledger chain.
        
        Returns:
            True if chain is intact, False if any link is broken
        """
        with self._lock:
            if not self._entries:
                return True
            
            for i, entry in enumerate(self._entries):
                # Verify entry hash
                expected_hash = compute_entry_hash(
                    entry.ledger_id,
                    entry.sequence_number,
                    entry.timestamp,
                    entry.audit_content_sha256,
                    entry.file_hash,
                    entry.penrose_hash,
                    entry.ledger_prev
                )
                if entry.entry_hash != expected_hash:
                    logger.error(f"Entry hash mismatch at sequence {i}")
                    return False
                
                # Verify ledger_prev link (except genesis)
                if i > 0:
                    prev_entry = self._entries[i - 1]
                    expected_prev = compute_ledger_prev(
                        prev_entry.entry_hash,
                        prev_entry.audit_content_sha256,
                        prev_entry.sequence_number
                    )
                    if entry.ledger_prev != expected_prev:
                        logger.error(f"ledger_prev mismatch at sequence {i}")
                        return False
                
                # Verify ledger_next link (except last entry)
                if i < len(self._entries) - 1:
                    next_entry = self._entries[i + 1]
                    expected_next = compute_ledger_next(
                        entry.entry_hash,
                        next_entry.audit_content_sha256,
                        next_entry.sequence_number
                    )
                    if entry.ledger_next != expected_next:
                        logger.error(f"ledger_next mismatch at sequence {i}")
                        return False
            
            return True
    
    def get_chain_length(self) -> int:
        """Get the current chain length."""
        with self._lock:
            return len(self._entries)
    
    def export_chain(self) -> List[Dict[str, Any]]:
        """Export the full chain as a list of dictionaries."""
        with self._lock:
            return [entry.to_dict() for entry in self._entries]


# ─── Global Ledger Instance ──────────────────────────────────────────────────

_global_ledger: Optional[LedgerChain] = None


def get_ledger() -> LedgerChain:
    """Get or create the global ledger chain instance."""
    global _global_ledger
    if _global_ledger is None:
        _global_ledger = LedgerChain()
    return _global_ledger


def reset_ledger() -> None:
    """Reset the global ledger (for testing)."""
    global _global_ledger
    _global_ledger = None
