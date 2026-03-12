from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel


class FileInfo(BaseModel):
    name: str
    size: int
    type: str


class KPI(BaseModel):
    id: str
    label: str
    value: str | int | float
    trend: str
    status: str
    description: Optional[str] = None


class VerificationStatus(BaseModel):
    status: str
    confidence: int
    timestamp: str
    checks: list[str]


# ─── PASS97 Extended Output Schemas ──────────────────────────────────────────

class RiskLevel(str, Enum):
    """Risk classification levels per PASS97 spec."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyType(str, Enum):
    """Types of anomalies detected during audit."""
    ENTROPY_LOW = "ENTROPY_LOW"
    BYTE_DIVERSITY_LOW = "BYTE_DIVERSITY_LOW"
    GODEL_TRIVIAL = "GODEL_TRIVIAL"
    PADIC_DEGENERATE = "PADIC_DEGENERATE"
    NTT_ENTROPY_LOW = "NTT_ENTROPY_LOW"
    KAG_BELOW_THRESHOLD = "KAG_BELOW_THRESHOLD"
    PENROSE_DEGENERATE = "PENROSE_DEGENERATE"
    FORMAT_INVALID = "FORMAT_INVALID"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"


class Anomaly(BaseModel):
    """A single anomaly detected during audit."""
    anomaly_type: AnomalyType
    stage: str  # Which pipeline stage detected it
    severity: RiskLevel
    message: str
    details: Optional[Dict[str, Any]] = None


class RiskBadge(BaseModel):
    """
    Risk assessment badge per PASS97 spec.
    
    Provides a visual indicator of audit risk level.
    """
    level: RiskLevel
    score: float  # 0-100 risk score
    label: str  # Human-readable label
    color: str  # Hex color for UI
    
    @classmethod
    def from_audit_score(cls, audit_score: float, failed_checks: int) -> "RiskBadge":
        """Create risk badge from audit results."""
        if failed_checks == 0 and audit_score >= 90:
            return cls(
                level=RiskLevel.LOW,
                score=audit_score,
                label="Low Risk",
                color="#22c55e"  # Green
            )
        elif failed_checks <= 1 and audit_score >= 70:
            return cls(
                level=RiskLevel.MEDIUM,
                score=audit_score,
                label="Medium Risk",
                color="#eab308"  # Yellow
            )
        elif failed_checks <= 2 and audit_score >= 50:
            return cls(
                level=RiskLevel.HIGH,
                score=audit_score,
                label="High Risk",
                color="#f97316"  # Orange
            )
        else:
            return cls(
                level=RiskLevel.CRITICAL,
                score=audit_score,
                label="Critical Risk",
                color="#ef4444"  # Red
            )


class EUAIActCategory(str, Enum):
    """EU AI Act risk categories."""
    UNACCEPTABLE = "UNACCEPTABLE"
    HIGH_RISK = "HIGH_RISK"
    LIMITED_RISK = "LIMITED_RISK"
    MINIMAL_RISK = "MINIMAL_RISK"


class EUAIActCompliance(BaseModel):
    """
    EU AI Act compliance assessment.
    
    PASS97 Spec: Provides mapping to EU AI Act risk categories
    based on audit results. This is informational only.
    """
    category: EUAIActCategory
    article_reference: str  # Relevant EU AI Act article
    requirements: List[str]  # Applicable requirements
    assessment: str  # Brief compliance assessment
    disclaimer: str  # Legal disclaimer
    
    @classmethod
    def from_risk_badge(cls, risk_badge: RiskBadge) -> "EUAIActCompliance":
        """Map PASS97 risk to EU AI Act category (informational)."""
        if risk_badge.level == RiskLevel.CRITICAL:
            return cls(
                category=EUAIActCategory.HIGH_RISK,
                article_reference="Article 6, Annex III",
                requirements=[
                    "Risk management system required",
                    "Data governance and documentation",
                    "Human oversight provisions",
                    "Accuracy, robustness, cybersecurity"
                ],
                assessment="Model weights may require HIGH_RISK compliance if deployed in listed use cases",
                disclaimer="This assessment is informational only. Consult legal counsel for official compliance determination."
            )
        elif risk_badge.level == RiskLevel.HIGH:
            return cls(
                category=EUAIActCategory.LIMITED_RISK,
                article_reference="Article 52",
                requirements=[
                    "Transparency obligations",
                    "User notification requirements"
                ],
                assessment="Model weights show elevated risk indicators; review before deployment",
                disclaimer="This assessment is informational only. Consult legal counsel for official compliance determination."
            )
        else:
            return cls(
                category=EUAIActCategory.MINIMAL_RISK,
                article_reference="Article 69",
                requirements=[
                    "Voluntary codes of conduct recommended"
                ],
                assessment="Model weights pass standard audit checks",
                disclaimer="This assessment is informational only. Consult legal counsel for official compliance determination."
            )


class LedgerInfo(BaseModel):
    """Ledger chain information for an audit entry."""
    ledger_id: str
    sequence_number: int
    prev_state: Optional[str] = None
    next_state_hash: Optional[str] = None
    audit_content_sha256: str
    entry_hash: str


class MapPosition(BaseModel):
    """Artifact coordinates on the Penrose map."""
    tau_vectors: List[float]
    barycentric: List[float]
    manifold_hash: str
    tile_hash: str


class ArtifactBlock(BaseModel):
    """Artifact blockchain block representing one resolved map position."""
    index: int
    timestamp: str
    artifact_hash: str
    tau_vectors: List[float]
    manifold_hash: str
    tile_hash: str
    barycentric: List[float]
    prev_block_hash: Optional[str] = None
    block_hash: str
    type: Optional[str] = None
    anchors: Optional[List[str]] = None


class LegalDisclosures(BaseModel):
    """
    Legal scope disclosures per PASS97 spec.
    
    Required disclosures about audit limitations.
    """
    weight_space_scope: str
    notified_body: Optional[str]
    out_of_scope: List[str]
    version: str
    
    @classmethod
    def default(cls) -> "LegalDisclosures":
        """Return standard PASS97 legal disclosures."""
        return cls(
            weight_space_scope=(
                "This audit evaluates static model weight artifacts only. "
                "The PASS97 pipeline examines cryptographic properties, structural "
                "integrity, and provenance markers within the serialized weight files. "
                "No inference, runtime behavior, or training data analysis is performed."
            ),
            notified_body=None,  # Set when certified
            out_of_scope=[
                "Runtime model behavior and inference outputs",
                "Training data composition and provenance",
                "Downstream application integration",
                "Hardware-specific execution characteristics",
                "Model fine-tuning or adaptation results",
                "Adversarial robustness under deployment",
                "Bias and fairness metrics (requires inference)",
                "Environmental and compute efficiency metrics"
            ],
            version="PASS97-v1.0-2026"
        )


class ExtendedAuditResult(BaseModel):
    """
    Extended audit result with all PASS97 spec fields.
    
    This is the full output contract including:
    - Anomalies list
    - Risk badge
    - EU AI Act table
    - Ledger information
    - Legal disclosures
    """
    # Core results (backward compatible)
    kpis: List[KPI]
    verification: VerificationStatus
    file_hash: str
    
    # Extended PASS97 fields
    anomalies: List[Anomaly]
    risk_badge: RiskBadge
    eu_ai_act: EUAIActCompliance
    ledger: Optional[LedgerInfo] = None
    legal_disclosures: LegalDisclosures
    
    # Penrose P3 details
    penrose_details: Optional[Dict[str, Any]] = None

    # Artifact map coordinates
    map_position: Optional[MapPosition] = None

    # Additive local artifact-position chain entry
    artifact_block: Optional[ArtifactBlock] = None
    
    # Tile hash for NFT
    tile_hash: Optional[str] = None
