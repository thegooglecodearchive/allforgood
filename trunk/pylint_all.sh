#!/bin/sh

FILES=`find . -mindepth 2 -name "*.py" \! -name "__*" \! -wholename "./datahub/dateutil/*" \! -wholename "./frontend/recaptcha.py" \! -wholename "./frontend/fastpageviews/*"`

{
for f in $FILES; do
  SCORE=`pylint $f 2>&1 | perl -ne 'm@Your code has been rated at ([0-9.-]+)@ && print "$1"'`
  echo "$SCORE $f"
done
} | sort -rn
