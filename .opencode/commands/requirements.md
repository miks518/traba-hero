---
description: Generate Functional (FR) and Non-Functional Requirements (NFR) as Markdown.
---

Perform an audit of the current codebase and project goals to generate a comprehensive `REQUIREMENTS.md` file in the project root.

Follow these rules strict adherence:
1. **Analyze Existing Code:** Read package manifests, architectural diagrams, API schemas, and current code structure to discover implicit requirements.
2. **Elicit Unclear Requirements:** If key parameters are missing (e.g., target user count, latency SLAs, compliance goals), stop and ask 2–3 targeted questions.
3. **Draft the Output:** Generate a well-formatted `.md` document using the exact structure outlined below.

## Requirements Document Structure

# Project Requirements Specification

## 1. Functional Requirements (FR)
Categorize features by module/domain. Every requirement must follow the format:
- **[FR-MODULE-001] Title**: Concise statement of what the system *shall* do.
  - *Description*: Detailed behavior and triggers.
  - *Acceptance Criteria*: Measurable bullet points.

## 2. Non-Functional Requirements (NFR)
Group into industry-standard quality attributes:
- **[NFR-PERF-001] Performance & Latency**: Response times, throughput, resource limits.
- **[NFR-SEC-001] Security & Compliance**: Auth, encryption, PII, rate limiting.
- **[NFR-RELI-001] Reliability & Availability**: Uptime, failover, disaster recovery.
- **[NFR-MAINT-001] Maintainability**: Test coverage, linter/type strictness, CI/CD pipeline checks.

## 3. Requirement Traceability Matrix (RTM)
A markdown table mapping FRs and NFRs to their corresponding codebase files/paths.

Save the final output directly to `./REQUIREMENTS.md`.