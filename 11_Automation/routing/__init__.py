"""Career_OS Stage 5B — application routing (downstream-only).

Reads existing Stage 4 job + provenance evidence and, optionally, re-polls
the existing Stage 4 connectors (read-only, public APIs) to verify a
vacancy is still live. Never writes back into 08_Job_Search/.
"""
