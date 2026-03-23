# RIMOS Documentation Index

> Complete documentation hub for the RIMOS project. Start here to find the right guide for your needs.

---

## How to Use This Documentation

### I am a NEW developer setting up RIMOS

**Start here:**

1. [SETUP_AND_INSTALLATION.md](./SETUP_AND_INSTALLATION.md) ← **Read this first**
    - Complete step-by-step setup for backend and frontend
    - System requirements and environment configuration
    - Troubleshooting common setup issues
    - Running tests

2. [COMPREHENSIVE_DEVELOPER_GUIDE.md](./COMPREHENSIVE_DEVELOPER_GUIDE.md)
    - Project overview and architecture
    - Complete pipeline process explanation
    - Detailed breakdown of all components
    - Data models and schemas

3. [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)
    - Keep this handy during development
    - Quick command lookup
    - Common debugging tips

**Time estimate:** 2-3 hours from download to first working build

---

### I need to INTEGRATE with RIMOS APIs

**Start here:**

1. [API_INTEGRATION_GUIDE.md](./API_INTEGRATION_GUIDE.md) ← **Read this first**
    - Detailed endpoint documentation
    - Request/response examples
    - Code samples (Python & TypeScript)
    - Error handling patterns

2. [QUICK_REFERENCE.md](./QUICK_REFERENCE.md#api-endpoints-cheat-sheet)
    - API endpoints quick lookup
    - Common error codes

**Time estimate:** 30 minutes - 2 hours depending on integration scope

---

### I need to UNDERSTAND the architecture

**Start here:**

1. [COMPREHENSIVE_DEVELOPER_GUIDE.md](./COMPREHENSIVE_DEVELOPER_GUIDE.md) ← **Read this first**
    - System diagram and architecture overview
    - Backend directory structure and key files
    - Frontend directory structure and components
    - Complete pipeline process with diagrams

2. [README.md](../README.md)
    - High-level project overview
    - Core concepts

**Time estimate:** 1-2 hours

---

### I need to UNDERSTAND the pipeline process

**Start here:**

1. [COMPREHENSIVE_DEVELOPER_GUIDE.md - Pipeline Section](./COMPREHENSIVE_DEVELOPER_GUIDE.md#pipeline-process-detailed) ← **Read this first**
    - Step-by-step pipeline walkthrough
    - Mathematical concepts (Gödel encoding, NTT, Penrose, etc.)
    - Audit engine logic
    - Risk score calculation

2. [QUICK_REFERENCE.md - Core Pipeline](./QUICK_REFERENCE.md#core-pipeline-5-steps)
    - Quick overview

3. Source code:
    - [rim_os_v2.py](../backend/rim_os_v2.py) - Audit engine implementation
    - [services/rim_wrapper.py](../backend/app/services/rim_wrapper.py) - Engine wrapper

**Time estimate:** 2-3 hours to fully understand

---

### I need to CONTRIBUTE code

**Start here:**

1. [SETUP_AND_INSTALLATION.md](./SETUP_AND_INSTALLATION.md#development-workflow)
    - Development workflow
    - Before-commit checklist

2. [COMPREHENSIVE_DEVELOPER_GUIDE.md - Backend/Frontend Sections](./COMPREHENSIVE_DEVELOPER_GUIDE.md#backend-development)
    - How to add endpoints
    - How to add services
    - How to add components
    - Code style guidelines

3. [QUICK_REFERENCE.md - Common Development Tasks](./QUICK_REFERENCE.md#common-development-tasks)
    - Quick reference for common tasks

**Important:** Run full test suite before committing:

```bash
cd backend
pytest
npm run lint && npm run type-check
```

---

### I need to DEBUG an issue

**Start here:**

1. [QUICK_REFERENCE.md - Troubleshooting](./QUICK_REFERENCE.md#troubleshooting)
    - Common errors and quick fixes

2. [SETUP_AND_INSTALLATION.md - Troubleshooting](./SETUP_AND_INSTALLATION.md#troubleshooting)
    - Detailed troubleshooting for setup issues

3. [COMPREHENSIVE_DEVELOPER_GUIDE.md - Troubleshooting](./COMPREHENSIVE_DEVELOPER_GUIDE.md#troubleshooting)
    - Common backend/frontend issues

**Debugging tips:**

```bash
# View logs
tail -f backend/logs/app.log

# Test backend is running
curl http://localhost:8000/docs

# Test frontend is running
curl http://localhost:3000

# View blockchain ledger
cat backend/data/artifact_chain.json | python -m json.tool
```

**Time estimate:** 15-30 minutes depending on issue

---

### I need to DEPLOY to production

**Start here:**

1. [SETUP_AND_INSTALLATION.md - Production Mode & Docker](./SETUP_AND_INSTALLATION.md#docker-setup-optional)
    - Production optimization tips
    - Docker setup

2. [COMPREHENSIVE_DEVELOPER_GUIDE.md - Infrastructure](./COMPREHENSIVE_DEVELOPER_GUIDE.md#infrastructure-concepts)
    - Architecture overview

**Note:** Production deployment not yet documented. Contact team lead.

---

## Documentation Map

### Core Documentation Files

| Document                                                               | Purpose                                         | Read Time  |
| ---------------------------------------------------------------------- | ----------------------------------------------- | ---------- |
| [SETUP_AND_INSTALLATION.md](./SETUP_AND_INSTALLATION.md)               | Complete setup guide for new developers         | 60-90 min  |
| [COMPREHENSIVE_DEVELOPER_GUIDE.md](./COMPREHENSIVE_DEVELOPER_GUIDE.md) | Detailed architecture and pipeline explanation  | 90-120 min |
| [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)                             | Quick lookup for commands, endpoints, debugging | 15-30 min  |
| [API_INTEGRATION_GUIDE.md](./API_INTEGRATION_GUIDE.md)                 | Complete API reference with code examples       | 60-90 min  |
| [DEVELOPER_GUIDE.md](./DEVELOPER_GUIDE.md)                             | Simple overview (existing)                      | 20 min     |
| [MILESTONE_4_DOCS_CONSISTENCY_FIXES.md](./MILESTONE_4_DOCS_CONSISTENCY_FIXES.md) | Contract corrections from client review | 15-20 min |

### Project Files

| File                                                           | Purpose                          |
| -------------------------------------------------------------- | -------------------------------- |
| [README.md](../README.md)                                      | Project introduction (existing)  |
| [MILESTONE_2_CLIENT_REPORT.md](./MILESTONE_2_CLIENT_REPORT.md) | Project status report (existing) |

---

## Quick Navigation by Topic

### Architecture & Design

- [System Diagram](./COMPREHENSIVE_DEVELOPER_GUIDE.md#system-diagram)
- [Data Flow Architecture](./COMPREHENSIVE_DEVELOPER_GUIDE.md#data-flow-architecture)
- [Backend Directory Structure](./COMPREHENSIVE_DEVELOPER_GUIDE.md#directory-structure)
- [Frontend Structure](./COMPREHENSIVE_DEVELOPER_GUIDE.md#directory-structure-1)

### Backend Development

- [Backend Setup](./SETUP_AND_INSTALLATION.md#backend-setup)
- [Backend Files Explained](./COMPREHENSIVE_DEVELOPER_GUIDE.md#core-backend-files-explained)
- [Data Models](./COMPREHENSIVE_DEVELOPER_GUIDE.md#backend-data-models-schemas)
- [Adding New Endpoints](./COMPREHENSIVE_DEVELOPER_GUIDE.md#add-new-api-endpoint)

### Frontend Development

- [Frontend Setup](./SETUP_AND_INSTALLATION.md#frontend-setup)
- [Components Explained](./COMPREHENSIVE_DEVELOPER_GUIDE.md#frontend-components-explained)
- [Adding New Component](./COMPREHENSIVE_DEVELOPER_GUIDE.md#add-frontend-component)

### Pipeline & Processing

- [Complete Pipeline Flow](./COMPREHENSIVE_DEVELOPER_GUIDE.md#complete-end-to-end-flow)
- [RIM-OS Audit Engine](./COMPREHENSIVE_DEVELOPER_GUIDE.md#rim-os-audit-engine-rim_os_v2py)
- [Mathematical Concepts](./COMPREHENSIVE_DEVELOPER_GUIDE.md#key-mathematical-concepts)
- [Risk Score Calculation](./QUICK_REFERENCE.md#risk-score-ranges)

### API Reference

- [Upload Endpoints](./API_INTEGRATION_GUIDE.md#upload-apis)
- [Report Endpoints](./API_INTEGRATION_GUIDE.md#report-apis)
- [NFT Minting Endpoints](./API_INTEGRATION_GUIDE.md#nft-minting-apis)
- [Error Handling](./API_INTEGRATION_GUIDE.md#error-handling)
- [Code Examples](./API_INTEGRATION_GUIDE.md#code-examples)

### Testing

- [Running Tests](./COMPREHENSIVE_DEVELOPER_GUIDE.md#testing)
- [Backend Testing](./COMPREHENSIVE_DEVELOPER_GUIDE.md#backend-testing)
- [Test Checklist](./QUICK_REFERENCE.md#testing-checklist)

### Debugging

- [Common Errors](./QUICK_REFERENCE.md#common-error-fixes)
- [Troubleshooting Backend](./SETUP_AND_INSTALLATION.md#pythonbackend-issues)
- [Troubleshooting Frontend](./SETUP_AND_INSTALLATION.md#nodejsfrontend-issues)
- [Debugging Commands](./QUICK_REFERENCE.md#debugging-commands)

### Configuration

- [Environment Variables](./QUICK_REFERENCE.md#environment-variables)
- [IDE Configuration](./SETUP_AND_INSTALLATION.md#ide-configuration)
- [Backend Config](./COMPREHENSIVE_DEVELOPER_GUIDE.md#backend-setup)

---

## File Location Reference

### Backend Key Files

**Entry Point:**

- `backend/app/main.py` - FastAPI application setup

**Core Engine:**

- `backend/rim_os_v2.py` - RIM-OS audit engine
- `backend/app/services/rim_wrapper.py` - Engine wrapper

**Routes (Endpoints):**

- `backend/app/routers/upload.py` - Single & chunked upload
- `backend/app/routers/report.py` - Report generation
- `backend/app/routers/mint.py` - NFT minting
- `backend/app/routers/ipfs.py` - IPFS metadata upload

**Services:**

- `backend/app/services/chunked_upload_service.py` - Upload management
- `backend/app/services/artifact_chain.py` - Blockchain ledger
- `backend/app/services/pdf_generator.py` - Report generation
- `backend/app/services/file_validation.py` - Validation
- `backend/eu_ai_act_layer.py` - EU AI Act Articles 9-15 enrichment

**Data & Models:**

- `backend/app/models/schemas.py` - Data structures
- `backend/data/artifact_chain.json` - Blockchain ledger
- `backend/data/report_cache/` - Report cache

**Tests:**

- `backend/tests/test_pipeline.py` - End-to-end tests
- `backend/tests/test_upload.py` - Upload tests
- `backend/tests/test_rimos_integration.py` - Audit engine tests

### Frontend Key Files

**Entry Point:**

- `web/src/app/page.tsx` - Landing page

**Pages:**

- `web/src/app/upload/page.tsx` - Upload page
- `web/src/app/report/[uploadId]/page.tsx` - Dynamic report page

**Components:**

- `web/src/components/FileUpload.tsx` - File upload UI
- `web/src/components/KPIDisplay.tsx` - Results display
- `web/src/components/BlockchainInfo.tsx` - Blockchain data
- `web/src/components/MintFlow.tsx` - NFT minting

**Utilities:**

- `web/src/app/upload/page.tsx` - Upload API orchestration
- `web/src/components/MintFlow.tsx` - Mint/IPFS API orchestration

---

## Technology Stack Summary

### Backend

- **Language:** Python 3.9+
- **Framework:** FastAPI (async web framework)
- **Validation:** Pydantic
- **Server:** Uvicorn (ASGI server)
- **Testing:** pytest
- **Key Libraries:** aiofiles, fpdf2, slowapi, solders

### Frontend

- **Framework:** Next.js 16 (React 19)
- **Language:** TypeScript
- **Styling:** Tailwind CSS 4
- **Blockchain:** Solana Web3.js, Metaplex
- **HTTP:** Axios
- **Animation:** Framer Motion

---

## Key Concepts Glossary

### RIMOS-Specific Terms

| Term                | Definition                                                                               |
| ------------------- | ---------------------------------------------------------------------------------------- |
| **Penrose Tiling**  | Infinite, aperiodic mathematical map used as artifact coordinate system                  |
| **Genesis Mints**   | Fixed reference anchors (fine-structure constant, Boltzmann entropy, Einstein equations) |
| **Tau Vectors**     | 5-dimensional coordinates of artifact on Penrose map                                     |
| **Artifact Block**  | Blockchain entry containing file hash, position, and metadata                            |
| **Integrity Score** | 0-100 metric combining entropy (30%), Penrose match (40%), anomalies (30%)               |
| **Risk Level**      | Classification: LOW (score ≥ 90), MEDIUM (70-89), HIGH (< 70)                            |

### Technical Terms

| Term               | Meaning                                                    |
| ------------------ | ---------------------------------------------------------- |
| **RIM-OS**         | Review & Integrity Mapping Operating System (audit engine) |
| **Gödel Encoding** | Method to convert binary data to prime exponents           |
| **p-adic Lift**    | Modular arithmetic conversion                              |
| **NTT**            | Number Theoretic Transform (FFT in finite field)           |
| **KAG Grid**       | 8×8 additive predictor for linear analysis                 |
| **Z-score**        | Standard deviation threshold for anomaly detection (±3σ)   |

---

## Common Questions

### Q: Where do I start as a new developer?

**A:** Follow this order:

1. [SETUP_AND_INSTALLATION.md](./SETUP_AND_INSTALLATION.md) - Get everything running
2. [COMPREHENSIVE_DEVELOPER_GUIDE.md](./COMPREHENSIVE_DEVELOPER_GUIDE.md) - Understand architecture
3. Explore source code - Start with `app/main.py` then `rim_os_v2.py`
4. Try uploading a file at http://localhost:3000

---

### Q: How does the audit pipeline work?

**A:** See [Pipeline Process (Detailed)](./COMPREHENSIVE_DEVELOPER_GUIDE.md#complete-end-to-end-flow) for complete walkthrough with diagrams.

**Quick version:**

1. File upload (single or chunked)
2. Validation (size, type, signature)
3. RIM-OS audit (Gödel → p-adic → NTT → KAG → Penrose)
4. Blockchain recording
5. Report generation
6. API response

---

### Q: What's the risk score based on?

**A:** Three factors:

- 30% Entropy (ideal ≈ 8 bits/byte)
- 40% Penrose match (how well it fits mathematical geometry)
- 30% Anomalies (fewer anomalies = better)

Result > score = base × (1 - bias_penalty)

Risk classification: HIGH (< 70), MEDIUM (70-89), LOW (≥ 90)

---

### Q: How do I add a new API endpoint?

**A:** See [Add New API Endpoint](./COMPREHENSIVE_DEVELOPER_GUIDE.md#add-new-api-endpoint) in development section.

**Quick steps:**

1. Create router in `app/routers/new_router.py`
2. Define Pydantic schemas
3. Implement business logic in service
4. Mount router in `app/main.py`

---

### Q: How do I run tests?

**A:**

```bash
cd backend
pytest                              # All tests
pytest tests/test_pipeline.py -v   # Specific test
pytest --cov=app tests/            # With coverage
```

---

### Q: How do I debug an issue?

**A:**

1. Check logs: `tail -f backend/logs/app.log`
2. Check browser DevTools (Network tab for frontend issues)
3. Verify backend is running: `curl http://localhost:8000/docs`
4. See [Troubleshooting](./SETUP_AND_INSTALLATION.md#troubleshooting) section

---

### Q: Can I use RIMOS without running locally?

**A:** Not yet. Currently requires local setup.

**Future:** Containerized version and cloud deployment planned.

---

## Getting Help

### Need help? Here's how to find answers:

1. **Check this documentation** - Most answers are here
2. **Search QUICK_REFERENCE.md** - Quick lookup for common issues
3. **Review test files** - Tests show how components work
4. **Check source code comments** - Many functions are well-documented
5. **Ask team members** - Share findings and help each other

---

## Documentation Maintenance

**Last Updated:** March 23, 2026
**Version:** 1.1
**Maintainer:** Development Team

### Updates needed for:

- [ ] Production deployment instructions
- [ ] Cloud deployment (AWS/Azure)
- [ ] Docker best practices
- [ ] Performance tuning guide
- [ ] Integration with external services
- [ ] Security hardening guide

---

## Having Trouble?

If you can't find what you need:

1. Check the [Table of Contents](#documentation-map) above
2. Search within documents (Ctrl+F or Cmd+F)
3. Review the git commit history: `git log --grep="your-topic"`
4. Check existing issues: `git issues`
5. Ask in team Slack/Discord

---

**Happy Coding! 🚀**

Start with [SETUP_AND_INSTALLATION.md](./SETUP_AND_INSTALLATION.md) and you'll be up and running in no time.
