#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
UPDATE_REMOTE="${UPDATE_REMOTE:-origin}"
UPDATE_BRANCH="${UPDATE_BRANCH:-}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"
DB_SERVICE="${DB_SERVICE:-db}"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/.deploy-backups}"
DEPLOY_STATE_FILE="${DEPLOY_STATE_FILE:-$REPO_ROOT/.deploy-state}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://127.0.0.1:8000/api/health/}"
HEALTHCHECK_HOST="${HEALTHCHECK_HOST:-}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-30}"
HEALTHCHECK_INTERVAL="${HEALTHCHECK_INTERVAL:-2}"
SKIP_DB_BACKUP="${SKIP_DB_BACKUP:-0}"
FORCE_REDEPLOY="${FORCE_REDEPLOY:-0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_FILE=""
CURRENT_STEP="初始化"

info() {
    echo -e "${BLUE}[update] $*${NC}"
}

success() {
    echo -e "${GREEN}[update] ✓ $*${NC}"
}

warn() {
    echo -e "${YELLOW}[update] ! $*${NC}"
}

die() {
    echo -e "${RED}[update] ✗ $*${NC}" >&2
    exit 1
}

on_error() {
    local exit_code="$1"
    local line_number="$2"

    echo -e "${RED}[update] ✗ 更新失败：${CURRENT_STEP}（行 ${line_number}，退出码 ${exit_code}）${NC}" >&2
    if [ -n "$BACKUP_FILE" ]; then
        echo -e "${YELLOW}[update] 数据库备份保留在：${BACKUP_FILE}${NC}" >&2
    fi
    if [ "${COMPOSE_READY:-0}" = "1" ]; then
        "${COMPOSE[@]}" -f "$COMPOSE_FILE" logs --tail=80 "$BACKEND_SERVICE" >&2 || true
    fi
    exit "$exit_code"
}

trap 'on_error "$?" "$LINENO"' ERR

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

resolve_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE=(docker-compose)
    else
        die "未找到 Docker Compose（docker compose 或 docker-compose）"
    fi
    COMPOSE_READY=1
}

container_is_running() {
    local service="$1"
    local container_id

    container_id="$("${COMPOSE[@]}" -f "$COMPOSE_FILE" ps -q "$service")"
    [ -n "$container_id" ] &&
        [ "$(docker inspect -f '{{.State.Running}}' "$container_id" 2>/dev/null)" = "true" ]
}

resolve_healthcheck_host() {
    local allowed_hosts

    if [ -n "$HEALTHCHECK_HOST" ]; then
        return
    fi

    allowed_hosts="$(
        sed -n 's/^[[:space:]]*ALLOWED_HOSTS[[:space:]]*=[[:space:]]*//p' .env |
            tail -n 1
    )"
    HEALTHCHECK_HOST="${allowed_hosts%%,*}"
    HEALTHCHECK_HOST="${HEALTHCHECK_HOST//[[:space:]]/}"

    if [ -z "$HEALTHCHECK_HOST" ] || [ "$HEALTHCHECK_HOST" = "*" ]; then
        HEALTHCHECK_HOST="localhost"
    fi
}

backup_database() {
    local timestamp
    local temporary_file

    if [ "$SKIP_DB_BACKUP" = "1" ]; then
        warn "已通过 SKIP_DB_BACKUP=1 跳过数据库备份"
        return
    fi

    CURRENT_STEP="备份 PostgreSQL"
    container_is_running "$DB_SERVICE" ||
        die "数据库服务 $DB_SERVICE 未运行，不能安全更新"

    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    install -d -m 700 "$BACKUP_DIR"
    temporary_file="$BACKUP_DIR/.database-${timestamp}.sql.tmp"
    BACKUP_FILE="$BACKUP_DIR/database-${timestamp}.sql"

    umask 077
    "${COMPOSE[@]}" -f "$COMPOSE_FILE" exec -T "$DB_SERVICE" \
        sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
        >"$temporary_file"
    [ -s "$temporary_file" ] || die "数据库备份为空"
    mv "$temporary_file" "$BACKUP_FILE"

    if command -v gzip >/dev/null 2>&1; then
        gzip -f "$BACKUP_FILE"
        BACKUP_FILE="${BACKUP_FILE}.gz"
    fi
    success "数据库已备份"
}

wait_for_healthcheck() {
    local attempt

    CURRENT_STEP="等待健康检查"
    resolve_healthcheck_host
    for ((attempt = 1; attempt <= HEALTHCHECK_RETRIES; attempt++)); do
        if curl --fail --silent --show-error --max-time 5 \
            -H "Host: $HEALTHCHECK_HOST" \
            "$HEALTHCHECK_URL" >/dev/null; then
            success "健康检查通过"
            return
        fi
        sleep "$HEALTHCHECK_INTERVAL"
    done

    die "健康检查失败：${HEALTHCHECK_URL}"
}

main() {
    local current_branch
    local current_commit
    local target_commit
    local deployed_commit
    local app_uid
    local app_gid

    require_command git
    require_command docker
    require_command curl
    require_command flock
    resolve_compose

    [ -f "$COMPOSE_FILE" ] || die "生产 Compose 文件不存在：$COMPOSE_FILE"
    [ -f ".env" ] || die "生产环境文件不存在：$REPO_ROOT/.env"
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 ||
        die "当前目录不是 Git 仓库"

    if ! git diff --quiet || ! git diff --cached --quiet; then
        die "存在未提交的已跟踪文件修改，请先处理后再更新"
    fi

    current_branch="$(git symbolic-ref --quiet --short HEAD)" ||
        die "当前处于 detached HEAD，请通过 UPDATE_BRANCH 指定并切换到部署分支"
    if [ -z "$UPDATE_BRANCH" ]; then
        UPDATE_BRANCH="$current_branch"
    fi
    [ "$current_branch" = "$UPDATE_BRANCH" ] ||
        die "当前分支是 $current_branch，但请求更新 $UPDATE_BRANCH"

    exec 9>"${TMPDIR:-/tmp}/work-order-backend-update.lock"
    flock -n 9 || die "已有另一个更新任务正在运行"

    info "仓库：$REPO_ROOT"
    info "更新目标：$UPDATE_REMOTE/$UPDATE_BRANCH"

    CURRENT_STEP="拉取远端源码"
    current_commit="$(git rev-parse HEAD)"
    git fetch --prune "$UPDATE_REMOTE" "$UPDATE_BRANCH"
    target_commit="$(git rev-parse FETCH_HEAD)"

    deployed_commit=""
    if [ -f "$DEPLOY_STATE_FILE" ]; then
        deployed_commit="$(sed -n '1p' "$DEPLOY_STATE_FILE")"
    fi
    if [ "$current_commit" = "$target_commit" ] &&
        [ "$deployed_commit" = "$target_commit" ] &&
        [ "$FORCE_REDEPLOY" != "1" ]; then
        success "源码和已部署版本均为最新：$(git rev-parse --short HEAD)"
        return
    fi
    if [ "$current_commit" = "$target_commit" ]; then
        warn "源码已是最新，但部署状态未确认，将重新部署当前版本"
    fi

    git merge-base --is-ancestor "$current_commit" "$target_commit" ||
        die "远端历史不是当前版本的 fast-forward，已拒绝自动更新"

    backup_database

    git merge --ff-only "$target_commit"
    success "源码已更新到 $(git rev-parse --short HEAD)"

    CURRENT_STEP="构建后端镜像"
    "${COMPOSE[@]}" -f "$COMPOSE_FILE" build --pull "$BACKEND_SERVICE"

    CURRENT_STEP="Django 系统检查"
    "${COMPOSE[@]}" -f "$COMPOSE_FILE" run --rm --no-deps -T \
        "$BACKEND_SERVICE" python manage.py check

    CURRENT_STEP="执行数据库迁移"
    "${COMPOSE[@]}" -f "$COMPOSE_FILE" run --rm --no-deps -T \
        "$BACKEND_SERVICE" python manage.py migrate --noinput

    CURRENT_STEP="检查静态目录权限"
    install -d media staticfiles
    if ! "${COMPOSE[@]}" -f "$COMPOSE_FILE" run --rm --no-deps -T \
        "$BACKEND_SERVICE" sh -c \
        'test -w /app/media && test -w /app/staticfiles'; then
        [ "$EUID" -eq 0 ] ||
            die "media/staticfiles 对容器用户不可写，请使用 root 修正目录属主"
        app_uid="$(
            "${COMPOSE[@]}" -f "$COMPOSE_FILE" run --rm --no-deps -T \
                "$BACKEND_SERVICE" id -u |
                tail -n 1
        )"
        app_gid="$(
            "${COMPOSE[@]}" -f "$COMPOSE_FILE" run --rm --no-deps -T \
                "$BACKEND_SERVICE" id -g |
                tail -n 1
        )"
        [[ "$app_uid" =~ ^[0-9]+$ && "$app_gid" =~ ^[0-9]+$ ]] ||
            die "无法确定容器用户 UID/GID"
        chown -R "$app_uid:$app_gid" media staticfiles
    fi

    CURRENT_STEP="收集静态文件"
    "${COMPOSE[@]}" -f "$COMPOSE_FILE" run --rm --no-deps -T \
        "$BACKEND_SERVICE" python manage.py collectstatic --noinput

    CURRENT_STEP="重建后端容器"
    "${COMPOSE[@]}" -f "$COMPOSE_FILE" up -d --no-deps \
        --force-recreate "$BACKEND_SERVICE"

    wait_for_healthcheck
    "${COMPOSE[@]}" -f "$COMPOSE_FILE" ps "$BACKEND_SERVICE"
    umask 077
    printf '%s\n' "$(git rev-parse HEAD)" >"${DEPLOY_STATE_FILE}.tmp"
    mv "${DEPLOY_STATE_FILE}.tmp" "$DEPLOY_STATE_FILE"
    success "更新完成：$(git rev-parse --short HEAD)"
}

main "$@"
