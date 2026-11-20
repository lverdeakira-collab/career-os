# Career_OS Two-Base Resume Routing Rules v1.0

The router performs two separate decisions:

1. Functional route classification.
2. Production base-resume selection.

## Functional routes

- Commercial / Research
- Corporate Finance / Transaction / Advisory
- Markets / FMI / FinTech

## Selectable production bases

- `COMMERCIAL_PRIMARY`
- `CF_TRANSACTION_SECONDARY`

No third base is permitted. The five resumes under `07_Generated_Resumes/` are immutable archive/provenance/regression assets and must never be returned for a new application.

## Evidence priority

1. Job responsibilities
2. Business function
3. Required skills
4. Job family
5. Industry context
6. Role title

Markets/FMI/FinTech selects the nearest evidence base. Research and commercial insight normally favor `COMMERCIAL_PRIMARY`; finance, banking, transaction, valuation, markets, and middle-office evidence normally favor `CF_TRANSACTION_SECONDARY`.

The router emits a functional `Primary_Route`, optional functional `Secondary_Route`, one `Recommended_Resume`, routing confidence, separate route/base scores, and an auditable reason. Bases are never merged.

Tailoring, when materially useful, must create a derived application asset. The two frozen Production Base v1.0 files must never be overwritten.
