#!/bin/zsh
# every check, in one go. Needs: python3 -m http.server 8899 &
#
# A failing test used to print its LAST LINE only -- "FAIL" -- and the reason went in the bin.
# Re-running to find out is a bet that it reproduces, which for a flaky one it does not. The
# whole output of anything that fails is kept, and repeated at the end where it can be read.
cd "$(dirname "$0")/.."
# Invoked as `bash tools/all.sh` this file used to print "print: command not found" for every
# test and still exit 0 -- a silent all-pass. Refuse rather than lie.
if [ -z "$ZSH_VERSION" ]; then
  echo "tools/all.sh needs zsh -- run it as 'tools/all.sh' or 'zsh tools/all.sh'" >&2
  exit 2
fi
fail=0
typeset -a broke
for t in js-check rules-test items-test hud-fit device-fit sound-test i18n-test tutorial-test relic-audit ads-test dev-test erode-test spawnbuy-test dt-test storage-test save-test coin-test coinfly-test art-check book-test menufx-test stack-test pair-audit smoke; do
  printf "%-15s " "$t"
  if out=$(python3 "tools/$t.py" 2>&1); then
    print -- "${out##*$'\n'}"
  else
    print -- "${out##*$'\n'}  <<< FAIL"
    fail=1
    broke+=("$t")
    print -r -- "$out" > "/tmp/fs-fail-$t.txt"
  fi
done
python3 tools/gen-catalog.py >/dev/null || fail=1
if (( ${#broke} )); then
  for t in $broke; do
    print -- "\n===== $t =====";
    tail -20 "/tmp/fs-fail-$t.txt"
    print -- "(전문: /tmp/fs-fail-$t.txt)"
  done
fi
exit $fail
