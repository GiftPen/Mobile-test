#!/bin/zsh
# every check, in one go. Needs: python3 -m http.server 8899 &
cd "$(dirname "$0")/.."
fail=0
for t in rules-test items-test hud-fit device-fit sound-test i18n-test tutorial-test relic-audit ads-test save-test coin-test coinfly-test art-check smoke; do
  printf "%-15s " "$t"
  if out=$(python3 "tools/$t.py" 2>&1); then print -- "${out##*$'\n'}"; else print -- "${out##*$'\n'}  <<< FAIL"; fail=1; fi
done
python3 tools/gen-catalog.py >/dev/null || fail=1
exit $fail
