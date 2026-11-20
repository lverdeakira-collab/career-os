# Synthetic test jobs

`synthetic_test_jobs.json` contains 12 fictional structures used only to validate logic. The company labels explicitly begin with “Synthetic”; they are not real openings and must not enter job discovery or candidate records.

Coverage:

1. Strong Risk / Banking fit
2. Strong Financial Analyst fit
3. Strong Business Strategy fit
4. Strong Business Analytics fit
5. Strong AI Business fit
6. Cross-functional multi-route role
7. Senior role hard failure
8. Unverified must-have skill → manual review
9. Preferred-skill-only gap
10. Mandatory-language ambiguity
11. Pure software-engineering AI role
12. Insufficient JD information

`expected_outcomes.json` asserts, for every job, the hard-gate status, the score-band decision, the final decision, the primary route and the recommended resume. `scripts/run_tests.sh` checks every field.

With the bundled synthetic profile the set covers every decision path: `PRIORITY_APPLY` (job 1), `APPLY` (jobs 2, 6, 9), `REVIEW` from the score band (jobs 3, 4, 5), `REVIEW` from a gate (jobs 8, 10, 12) and `SKIP` from a gate failure (jobs 7, 11).
