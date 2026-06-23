#!/usr/bin/env bash
# =============================================================================
# fly-init.sh — Sincronizador de estado del stack en Fly.io
#
# Modelo mental: reconciliación tipo Terraform/Kubernetes.
#   - Lee el estado actual (apps, db, bucket, secrets, objetos).
#   - Aplica solo el delta para llevarlo al estado deseado.
#   - Idempotente: ejecutar N veces es seguro y converge.
#   - CI-friendly: sin prompts, exit codes claros, log estructurado.
#
# Recursos gestionados:
#   - 3 apps: mortalidad-api, mortalidad-dashboard, mortalidad-etl
#   - 1 cluster Postgres + attach con users distintos por app
#   - 1 bucket Tigris (con fallback de nombre si está en cooldown)
#   - CSV en Tigris (head_object check, re-upload si difiere)
#   - Secrets (DATABASE_URL via attach, GRANT_USERS, CSV_URL, DASHBOARD_ORIGIN)
#   - 3 deploys (Fly compara image hash)
#   - Machine start del ETL (no-op si ya está running)
# =============================================================================
set -euo pipefail

# ---- Configuración (override vía env vars) ----
API_APP="${API_APP:-mortalidad-api}"
DASH_APP="${DASH_APP:-mortalidad-dashboard}"
ETL_APP="${ETL_APP:-mortalidad-etl}"
DB_APP="${DB_APP:-mortalidad-db}"
DB_NAME="${DB_NAME:-mortalidad}"
API_DB_USER="${API_DB_USER:-mortalidad}"
ETL_DB_USER="${ETL_DB_USER:-mortalidad_etl}"
BUCKET_NAME_BASE="${BUCKET_NAME_BASE:-mortalidad-csv}"
REGION="${FLY_REGION:-gru}"
CSV_LOCAL="${CSV_LOCAL:-data/raw/defunciones-ocurridas-y-registradas-en-la-republica-argentina-entre-los-anos-2005-2022.csv}"
CSV_REMOTE_KEY="${CSV_REMOTE_KEY:-defunciones.csv}"
ORG="${FLY_ORG:-personal}"

# Modos de operación
NO_DEPLOY="${NO_DEPLOY:-0}"
NO_START_ETL="${NO_START_ETL:-0}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# ---- Logging estructurado ----
log()  { printf "\033[1;34m[sync]\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m[ ok ]\033[0m %s\n" "$*"; }
diff_() { printf "\033[1;36m[diff]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*" >&2; }
fail() { printf "\033[1;31m[fail]\033[0m %s\n" "$*" >&2; }

# ---- Pre-flight ----
command -v fly >/dev/null 2>&1 \
  || { fail "flyctl no instalado. https://fly.io/docs/hands-on/install-flyctl/"; exit 1; }
fly auth whoami >/dev/null 2>&1 \
  || { fail "No estás logueado. Corre 'fly auth login' o exporta FLY_API_TOKEN."; exit 1; }
command -v python3 >/dev/null 2>&1 \
  || { fail "python3 no instalado (necesario para sincronizar CSV en Tigris)."; exit 1; }

# ---- Helpers ----
app_exists()       { fly status --app "$1" >/dev/null 2>&1; }
has_db_url()       { fly secrets list --app "$1" 2>/dev/null | grep -q DATABASE_URL; }
bucket_exists()    { fly storage list 2>/dev/null | awk '{print $1}' | grep -qx "$1"; }
# Field names en el JSON de 'fly secrets list -j' son lowercase ('name', 'digest').
# El '|| true' evita que pipefail mate el script si python falla por la razón que sea.
sec_value_digest() {
  fly secrets list --app "$1" -j 2>/dev/null \
    | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(next((s.get('digest', '') for s in d if s.get('name') == '$2'), ''))
except Exception:
    print('')
" 2>/dev/null || true
}

# ============================================================
# 1. Apps (mortalidad-api, mortalidad-dashboard, mortalidad-etl)
# ============================================================
ensure_app() {
  local name="$1"
  if app_exists "$name"; then
    ok "app $name presente"
  else
    diff_ "creando app $name"
    fly apps create "$name" --org "$ORG" >/dev/null
  fi
}

log "==> Reconciliando apps"
ensure_app "$API_APP"
ensure_app "$DASH_APP"
ensure_app "$ETL_APP"

# ============================================================
# 2. Postgres cluster
# ============================================================
log "==> Reconciliando Postgres"
if app_exists "$DB_APP"; then
  ok "postgres $DB_APP presente"
else
  diff_ "creando postgres $DB_APP en $REGION"
  fly postgres create \
      --name "$DB_APP" \
      --region "$REGION" \
      --initial-cluster-size 1 \
      --vm-size shared-cpu-1x \
      --volume-size 1 \
      --password "$(openssl rand -hex 16)" \
      --org "$ORG"
fi

# ============================================================
# 3. Attach Postgres a apps (con cleanup de users huérfanos)
# ============================================================
ensure_attach() {
  local target="$1"
  local user="$2"

  if has_db_url "$target"; then
    ok "$target -> $DB_APP attach presente"
    return 0
  fi

  diff_ "attach $DB_APP -> $target (db=$DB_NAME, user=$user)"
  local attach_log
  attach_log=$(mktemp)
  if fly postgres attach "$DB_APP" --app "$target" \
        --database-name "$DB_NAME" --database-user "$user" --yes 2>&1 | tee "$attach_log"; then
    rm -f "$attach_log"
    return 0
  fi

  # Caso B: user huérfano de un app destruida previamente
  if grep -qE "already exists" "$attach_log"; then
    warn "User '$user' huérfano del estado previo. Intentando cleanup vía ssh a $DB_APP..."
    if fly ssh console --app "$DB_APP" -C "psql -U postgres -c \"DROP USER IF EXISTS $user CASCADE;\"" 2>&1 \
         | grep -qE "DROP ROLE|does not exist"; then
      diff_ "user removido — reintentando attach"
      if fly postgres attach "$DB_APP" --app "$target" \
            --database-name "$DB_NAME" --database-user "$user" --yes; then
        rm -f "$attach_log"
        return 0
      fi
    fi
    warn "Cleanup automático del user falló. Hacelo a mano:"
    warn "  fly ssh console --app $DB_APP -C \"psql -U postgres -c 'DROP USER IF EXISTS $user CASCADE;'\""
    warn "  y vuelve a correr el script."
  fi
  rm -f "$attach_log"
  fail "attach $target falló."
  return 1
}

log "==> Reconciliando attach Postgres"
ensure_attach "$API_APP" "$API_DB_USER"
ensure_attach "$ETL_APP" "$ETL_DB_USER"

# ============================================================
# 4. Secrets cross-app
# ============================================================
ensure_secret() {
  # ensure_secret <app> <key> <desired-value>
  local app="$1" key="$2" desired="$3"
  local current
  current=$(sec_value_digest "$app" "$key")
  # Fly no expone valores, solo digests. Si el secret ya existe, asumimos OK.
  # Si querés forzar reset, exportá FORCE_RESET_SECRETS=1.
  if [ -n "$current" ] && [ "${FORCE_RESET_SECRETS:-0}" != "1" ]; then
    ok "$app: $key ya seteado (digest $current)"
    return 0
  fi
  diff_ "$app: setando $key"
  fly secrets set "$key"="$desired" --app "$app" --stage >/dev/null
}

log "==> Reconciliando secrets"
ensure_secret "$ETL_APP" GRANT_USERS "$API_DB_USER"
ensure_secret "$API_APP" DASHBOARD_ORIGIN "https://${DASH_APP}.fly.dev"

# ============================================================
# 5. Tigris bucket (con fallback de nombre por cooldown)
# ============================================================
TIGRIS_CREDS_FILE=""
ensure_bucket() {
  local primary="$BUCKET_NAME_BASE"

  if bucket_exists "$primary"; then
    ok "bucket Tigris $primary presente"
    export BUCKET_NAME="$primary"
    return 0
  fi

  TIGRIS_CREDS_FILE=$(mktemp)
  trap 'rm -f "$TIGRIS_CREDS_FILE"' EXIT

  diff_ "creando bucket Tigris $primary asociado a $ETL_APP"
  if fly storage create --name "$primary" --app "$ETL_APP" --yes 2>&1 | tee "$TIGRIS_CREDS_FILE"; then
    export BUCKET_NAME="$primary"
    return 0
  fi

  # Cooldown: usar nombre con timestamp
  if grep -qE "recently deleted|unavailable" "$TIGRIS_CREDS_FILE"; then
    local fallback="${primary}-$(date +%s)"
    warn "Bucket '$primary' en cooldown post-destroy. Usando '$fallback'."
    : > "$TIGRIS_CREDS_FILE"
    fly storage create --name "$fallback" --app "$ETL_APP" --yes 2>&1 | tee "$TIGRIS_CREDS_FILE"
    export BUCKET_NAME="$fallback"
    return 0
  fi
  fail "Bucket create falló."
  return 1
}

log "==> Reconciliando Tigris bucket"
ensure_bucket

# ============================================================
# 6. CSV en Tigris (sync vía head_object + boto3)
# ============================================================
ensure_python_boto3() {
  if python3 -c "import boto3" 2>/dev/null; then
    PY=python3
    return
  fi
  # Si estamos en CI con setup-python, el pip funciona
  if pip install --quiet boto3 2>/dev/null && python3 -c "import boto3" 2>/dev/null; then
    PY=python3
    return
  fi
  # Local: venv efímero
  VENV_DIR="${VENV_DIR:-/tmp/.fly-sync-venv}"
  if [ ! -d "$VENV_DIR" ]; then
    diff_ "creando venv en $VENV_DIR con boto3"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet boto3
  fi
  PY="$VENV_DIR/bin/python"
}

ensure_csv_in_tigris() {
  ensure_python_boto3

  # Obtener credenciales del bucket
  local akid secret endpoint
  if [ -n "$TIGRIS_CREDS_FILE" ] && [ -s "$TIGRIS_CREDS_FILE" ] \
       && grep -qE "AWS_ACCESS_KEY_ID:" "$TIGRIS_CREDS_FILE"; then
    akid=$(grep -E "AWS_ACCESS_KEY_ID:"     "$TIGRIS_CREDS_FILE" | awk '{print $2}')
    secret=$(grep -E "AWS_SECRET_ACCESS_KEY:" "$TIGRIS_CREDS_FILE" | awk '{print $2}')
    endpoint=$(grep -E "AWS_ENDPOINT_URL_S3:" "$TIGRIS_CREDS_FILE" | awk '{print $2}')
  else
    warn "Sin credenciales nuevas de Tigris. Si el bucket ya existía con CSV, asumo en sincronía."
    warn "Para forzar re-upload borra el objeto manualmente con: aws s3 rm s3://$BUCKET_NAME/$CSV_REMOTE_KEY"
    return 0
  fi
  endpoint="${endpoint:-https://fly.storage.tigris.dev}"

  if [ -f "$CSV_LOCAL" ]; then
    diff_ "sincronizando CSV: local -> s3://$BUCKET_NAME/$CSV_REMOTE_KEY"
    AWS_ACCESS_KEY_ID="$akid" \
    AWS_SECRET_ACCESS_KEY="$secret" \
    AWS_ENDPOINT_URL_S3="$endpoint" \
    AWS_REGION="auto" \
    "$PY" scripts/upload_csv_to_tigris.py sync \
        "$BUCKET_NAME" "$CSV_REMOTE_KEY" "$CSV_LOCAL"
  else
    # Sin CSV local: verificar que esté en el bucket
    if AWS_ACCESS_KEY_ID="$akid" \
       AWS_SECRET_ACCESS_KEY="$secret" \
       AWS_ENDPOINT_URL_S3="$endpoint" \
       AWS_REGION="auto" \
       "$PY" scripts/upload_csv_to_tigris.py check "$BUCKET_NAME" "$CSV_REMOTE_KEY"; then
      ok "CSV remoto presente (no hay archivo local para comparar)"
    else
      warn "CSV remoto AUSENTE y sin archivo local. Subílo manualmente:"
      warn "  python scripts/upload_csv_to_tigris.py sync $BUCKET_NAME $CSV_REMOTE_KEY <ruta-local>"
    fi
  fi
}

log "==> Reconciliando objeto CSV en Tigris"
ensure_csv_in_tigris
ensure_secret "$ETL_APP" CSV_URL "s3://${BUCKET_NAME}/${CSV_REMOTE_KEY}"

# ============================================================
# 7. Deploys (idempotentes: Fly compara image hash + config)
# ============================================================
if [ "$NO_DEPLOY" = "1" ]; then
  warn "NO_DEPLOY=1 — salteo deploys"
else
  log "==> Reconciliando deploys"
  diff_ "deploy api"
  fly deploy -c fly/api.fly.toml --app "$API_APP" --remote-only

  diff_ "deploy dashboard"
  fly deploy -c fly/dashboard.fly.toml --app "$DASH_APP" --remote-only

  diff_ "deploy etl (job)"
  fly deploy -c fly/etl.fly.toml --app "$ETL_APP" --remote-only --strategy immediate
fi

# ============================================================
# 8. Arrancar máquina del ETL para que bootstrap corra
# ============================================================
if [ "$NO_START_ETL" = "1" ]; then
  warn "NO_START_ETL=1 — no arranco máquina ETL"
else
  log "==> Reconciliando ejecución ETL bootstrap"
  ETL_MACHINE=$(fly machines list --app "$ETL_APP" 2>&1 | awk '/^ +[a-f0-9]+ /{print $1; exit}')
  if [ -n "$ETL_MACHINE" ]; then
    STATE=$(fly machines list --app "$ETL_APP" 2>&1 | awk -v id="$ETL_MACHINE" '$1==id{print $4; exit}')
    if [ "$STATE" = "started" ]; then
      ok "etl machine $ETL_MACHINE ya en started"
    else
      diff_ "arrancando etl machine $ETL_MACHINE"
      fly machine start "$ETL_MACHINE" --app "$ETL_APP" 2>&1 | tail -2 || true
    fi
  else
    warn "No detecté machine ID del ETL. Arráncalo manualmente."
  fi
fi

# ============================================================
# Reporte final
# ============================================================
cat <<EOF

✅ Estado reconciliado.

 API:        https://${API_APP}.fly.dev/docs
 Dashboard:  https://${DASH_APP}.fly.dev
 Postgres:   ${DB_APP}.internal:5432  (db=${DB_NAME}, privado)
 Tigris:     s3://${BUCKET_NAME}/${CSV_REMOTE_KEY}  (privado)

Ver bootstrap en vivo:   fly logs --app ${ETL_APP}
Re-ejecutar ETL:         fly machine start \$(fly machines list --app ${ETL_APP} -q | head -1) --app ${ETL_APP}

EOF
