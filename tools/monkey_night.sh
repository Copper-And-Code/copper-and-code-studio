#!/usr/bin/env bash
# The monkey of tests/manual/test_monkey.py for hours, one seed after the other, in every state.
#
#   tools/monkey_night.sh            # 8 hours, 3000 steps a run
#   tools/monkey_night.sh 2 1500     # 2 hours, 1500 steps a run
#
# Each run is a new process, so a crash ends only that run. The runs that fail keep, in
# build/manual/monkey-night/<start>/seed-<seed>/, the output of pytest (with the Python stack of
# a crash) and the steps of each state up to the last one; summary.txt lists every run.
# Offscreen, so it can run while the PC is used; it never reaches a real board.
set -uo pipefail
cd "$(dirname "$0")/.."
hours="${1:-8}"
steps="${2:-3000}"
folder="build/manual/monkey-night/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$folder"
end=$(( $(date +%s) + hours * 3600 ))
seed=$(( $(date +%s) % 100000 ))
runs=0
failed=0
echo "monkey for ${hours} h, ${steps} steps a run; reports in ${folder}"
while [ "$(date +%s)" -lt "$end" ]; do
    runs=$((runs + 1))
    output="$folder/run.out"
    LMS_MONKEY_SEED="$seed" LMS_MONKEY_STEPS="$steps" QT_QPA_PLATFORM=offscreen \
        timeout $(( steps * 3 + 600 )) .venv/bin/python -X faulthandler -m pytest -q -s -p no:faulthandler \
        tests/manual/test_monkey.py --manual >"$output" 2>&1
    code=$?
    if [ $code -eq 0 ]; then
        echo "seed ${seed}: passed" | tee -a "$folder/summary.txt"
    else
        failed=$((failed + 1))
        kept="$folder/seed-${seed}"
        mkdir -p "$kept"
        mv "$output" "$kept/pytest.out"
        cp build/manual/monkey-*.log "$kept/" 2>/dev/null || true
        reason=$(grep -m1 -E "Fatal Python error|^E   +step|^E +AssertionError" "$kept/pytest.out" | cut -c1-160)
        echo "seed ${seed}: FAILED (exit ${code}) ${reason}" | tee -a "$folder/summary.txt"
    fi
    seed=$((seed + 10))
done
rm -f "$folder/run.out"
echo "${runs} runs, ${failed} failed: ${folder}/summary.txt" | tee -a "$folder/summary.txt"
