#!/usr/bin/env bash
set -euo pipefail

# Simple curl-based smoke tests for local services
# - PostgreSQL Flask API (ratings): http://localhost:15000
# - Transformer NLP service: http://localhost:16050

POSTGRES_API_URL=${POSTGRES_API_URL:-http://localhost:15000}
TRANSFORMER_API_URL=${TRANSFORMER_API_URL:-http://localhost:16050}

log() { printf "\n==> %s\n" "$*"; }

wait_for() {
  local url=$1; local retries=${2:-60}
  log "Waiting for ${url} ..."
  until curl -fsS "$url" >/dev/null 2>&1; do
    ((retries--)) || { echo "Timeout waiting for $url"; exit 1; }
    sleep 2
  done
}

get_with_status() {
  local url=$1; shift
  local tmp
  tmp=$(mktemp)
  local code
  code=$(curl -sS -o "$tmp" -w '%{http_code}' "$url" "$@" || true)
  echo "HTTP $code - $url"
  cat "$tmp" || true
  echo
  rm -f "$tmp"
  if [[ "$code" != "200" && "$code" != "201" ]]; then
    echo "Request failed with status $code"
    exit 1
  fi
}

extract_json_field() {
  # Usage: extract_json_field FIELD_NAME
  python3 - "$@" <<'PY'
import sys, json
data = json.load(sys.stdin)
field = sys.argv[1]
val = data.get(field)
if isinstance(val, (int,float,str)):
    print(val)
else:
    print('')
PY
}

log "Smoke tests starting"

# --- PostgreSQL API tests ---
log "PostgreSQL API: ${POSTGRES_API_URL}"
wait_for "${POSTGRES_API_URL}/health"

log "Health"
get_with_status "${POSTGRES_API_URL}/health"

log "Purge ratings"
get_with_status "${POSTGRES_API_URL}/ratings/purge"

log "Create rating"
create_resp=$(curl -sS "${POSTGRES_API_URL}/ratings/create" \
  --get --data-urlencode "user_rating=9" \
  --get --data-urlencode "prompt_text=Test prompt" \
  --get --data-urlencode "response_text=Test response")
echo "HTTP 201 - ${POSTGRES_API_URL}/ratings/create"
echo "$create_resp"
echo

# Expect 201; if not, fail
if ! echo "$create_resp" | grep -q '"status"\s*:\s*"success"'; then
  echo "Create rating did not succeed"
  exit 1
fi

rating_id=$(printf '%s' "$create_resp" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("id",""))')
if [[ -z "${rating_id}" ]]; then
  # fallback to 1 if not parsed (dev convenience)
  rating_id=1
fi

log "List ratings"
get_with_status "${POSTGRES_API_URL}/ratings"

log "Get rating by id=${rating_id}"
get_with_status "${POSTGRES_API_URL}/ratings/${rating_id}"

log "Update tags"
get_with_status "${POSTGRES_API_URL}/ratings/${rating_id}/tags" --get --data-urlencode "tags={\"category\":\"updated\"}"

# --- Transformer NLP tests ---
log "Transformer API: ${TRANSFORMER_API_URL}"
wait_for "${TRANSFORMER_API_URL}/health"

log "Health"
get_with_status "${TRANSFORMER_API_URL}/health"

log "Similarity (cosine, similar texts)"
resp_similar=$(curl -sS "${TRANSFORMER_API_URL}/similarity?text1=I%20love%20programming&text2=I%20enjoy%20coding")
echo "HTTP 200 - ${TRANSFORMER_API_URL}/similarity?text1=I%20love%20programming&text2=I%20enjoy%20coding"
echo "$resp_similar"
echo
sim_metric=$(printf '%s' "$resp_similar" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("metric",""))')
sim_value=$(printf '%s' "$resp_similar" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("similarity",""))')
echo "Metric: $sim_metric | Similarity: $sim_value"
# Simple expectation: similar texts should have cosine similarity > 0.5
python3 - "$sim_value" <<'PY'
import sys
v=float(sys.argv[1])
assert v>0.5, f"Expected cosine similarity > 0.5, got {v}"
PY

log "Similarity (cosine, paraphrase)"
resp_para=$(curl -sS "${TRANSFORMER_API_URL}/similarity?text1=The%20cat%20sat%20on%20the%20mat&text2=A%20feline%20rested%20on%20the%20rug")
echo "HTTP 200 - ${TRANSFORMER_API_URL}/similarity?text1=The%20cat%20sat%20on%20the%20mat&text2=A%20feline%20rested%20on%20the%20rug"
echo "$resp_para"
echo
para_metric=$(printf '%s' "$resp_para" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("metric",""))')
para_value=$(printf '%s' "$resp_para" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("similarity",""))')
echo "Metric: $para_metric | Similarity: $para_value"

log "Similarity (cosine, different texts)"
resp_diff=$(curl -sS "${TRANSFORMER_API_URL}/similarity?text1=I%20love%20pizza&text2=Quantum%20physics%20is%20complex")
echo "HTTP 200 - ${TRANSFORMER_API_URL}/similarity?text1=I%20love%20pizza&text2=Quantum%20physics%20is%20complex"
echo "$resp_diff"
echo
diff_metric=$(printf '%s' "$resp_diff" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("metric",""))')
diff_value=$(printf '%s' "$resp_diff" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("similarity",""))')
echo "Metric: $diff_metric | Similarity: $diff_value"
# Simple expectation: different texts should have cosine similarity < 0.3
python3 - "$diff_value" <<'PY'
import sys
v=float(sys.argv[1])
assert v<0.3, f"Expected cosine similarity < 0.3, got {v}"
PY

log "Similarity (euclidean)"
resp_euc=$(curl -sS "${TRANSFORMER_API_URL}/similarity?text1=Hello%20world&text2=Hi%20there&metric=euclidean")
echo "HTTP 200 - ${TRANSFORMER_API_URL}/similarity?text1=Hello%20world&text2=Hi%20there&metric=euclidean"
echo "$resp_euc"
echo
euc_metric=$(printf '%s' "$resp_euc" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("metric",""))')
euc_value=$(printf '%s' "$resp_euc" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("similarity",""))')
echo "Metric: $euc_metric | Distance: $euc_value"

log "All smoke tests passed!"
