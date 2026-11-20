#!/usr/bin/env bash
# Run the Career OS validation suites against the bundled synthetic data.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${TMPDIR:-/tmp}/career_os_tests"
mkdir -p "$OUT"
export PYTHONDONTWRITEBYTECODE=1

status=0
for suite in run_experience_consumer_tests run_location_employment_gate_tests \
             run_routing_tests run_work_authorization_facts_tests; do
  python3 "11_Automation/validation/${suite}.py" --output "$OUT/${suite}.json" > /dev/null
  result=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['overall_status'])" "$OUT/${suite}.json")
  printf '%-40s %s\n' "$suite" "$result"
  [ "$result" = "PASS" ] || status=1
done

python3 -m unittest discover -s tests -q 2>"$OUT/unit.log" && printf '%-40s %s\n' "unit tests" "PASS" || { printf '%-40s %s\n' "unit tests" "FAIL (see $OUT/unit.log)"; status=1; }

python3 15_Application_Engine/run_dry_run.py \
  --input 15_Application_Engine/test_jobs/synthetic_test_jobs.json \
  --output "$OUT/dry_run.json" > /dev/null
python3 - "$OUT/dry_run.json" 15_Application_Engine/test_jobs/expected_outcomes.json <<'PY' || status=1
import json, sys
results = {job['Job_ID']: job for job in json.load(open(sys.argv[1]))}
expected = json.load(open(sys.argv[2]))
bad = [f"{jid}:{k}" for jid, exp in expected.items() for k, v in exp.items() if results.get(jid, {}).get(k) != v]
missing = sorted(set(expected) - set(results))
ok = not bad and not missing
print(f"{'dry_run vs expected outcomes (all fields)':<40} {'PASS' if ok else 'FAIL ' + ', '.join(bad + missing)}")
bad = bad + missing
sys.path.insert(0, '11_Automation')
from qa.schema_validation import validate_schema
schema = json.load(open('11_Automation/schemas/job.schema.json'))
schema_errors = [e for job in results.values() for e in validate_schema(job, schema, job['Job_ID'])]
print(f"{'dry_run output vs job schema':<40} {'PASS' if not schema_errors else 'FAIL ' + '; '.join(schema_errors[:3])}")
sys.exit(1 if bad or schema_errors else 0)
PY
exit $status
