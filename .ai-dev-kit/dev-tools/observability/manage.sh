#!/bin/bash
# Observability Dashboard Manager
# Usage: ./manage.sh [start|stop|restart|status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$SCRIPT_DIR/server"
CLIENT_DIR="$SCRIPT_DIR/client"
SERVER_PID_FILE="$SCRIPT_DIR/.server.pid"
CLIENT_PID_FILE="$SCRIPT_DIR/.client.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    if ! command -v bun &> /dev/null; then
        log_error "bun is required but not installed."
        log_info "Install: curl -fsSL https://bun.sh/install | bash"
        exit 1
    fi
}

start_server() {
    if [ -f "$SERVER_PID_FILE" ] && kill -0 "$(cat "$SERVER_PID_FILE")" 2>/dev/null; then
        log_warn "Server already running (PID: $(cat "$SERVER_PID_FILE"))"
        return 0
    fi

    log_info "Starting observability server..."
    cd "$SERVER_DIR"

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        log_info "Installing server dependencies..."
        bun install
    fi

    # Start server in background
    bun run src/index.ts &
    SERVER_PID=$!
    echo $SERVER_PID > "$SERVER_PID_FILE"

    # Wait for server to be ready
    sleep 2
    if curl -s "http://localhost:4000/health" > /dev/null 2>&1; then
        log_info "Server started on http://localhost:4000 (PID: $SERVER_PID)"
    else
        log_warn "Server started but health check failed - may still be initializing"
    fi
}

start_client() {
    if [ -f "$CLIENT_PID_FILE" ] && kill -0 "$(cat "$CLIENT_PID_FILE")" 2>/dev/null; then
        log_warn "Client already running (PID: $(cat "$CLIENT_PID_FILE"))"
        return 0
    fi

    log_info "Starting observability client..."
    cd "$CLIENT_DIR"

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        log_info "Installing client dependencies..."
        bun install
    fi

    # Start client in background
    bun run dev &
    CLIENT_PID=$!
    echo $CLIENT_PID > "$CLIENT_PID_FILE"

    sleep 3
    log_info "Client started on http://localhost:5173 (PID: $CLIENT_PID)"
}

stop_server() {
    if [ -f "$SERVER_PID_FILE" ]; then
        SERVER_PID=$(cat "$SERVER_PID_FILE")
        if kill -0 "$SERVER_PID" 2>/dev/null; then
            log_info "Stopping server (PID: $SERVER_PID)..."
            kill "$SERVER_PID" 2>/dev/null || true
            rm -f "$SERVER_PID_FILE"
            log_info "Server stopped"
        else
            log_warn "Server process not found, cleaning up PID file"
            rm -f "$SERVER_PID_FILE"
        fi
    else
        log_warn "Server not running (no PID file)"
    fi
}

stop_client() {
    if [ -f "$CLIENT_PID_FILE" ]; then
        CLIENT_PID=$(cat "$CLIENT_PID_FILE")
        if kill -0 "$CLIENT_PID" 2>/dev/null; then
            log_info "Stopping client (PID: $CLIENT_PID)..."
            kill "$CLIENT_PID" 2>/dev/null || true
            rm -f "$CLIENT_PID_FILE"
            log_info "Client stopped"
        else
            log_warn "Client process not found, cleaning up PID file"
            rm -f "$CLIENT_PID_FILE"
        fi
    else
        log_warn "Client not running (no PID file)"
    fi
}

show_status() {
    echo ""
    echo "Observability Dashboard Status"
    echo "==============================="
    echo ""

    # Server status
    if [ -f "$SERVER_PID_FILE" ] && kill -0 "$(cat "$SERVER_PID_FILE")" 2>/dev/null; then
        SERVER_PID=$(cat "$SERVER_PID_FILE")
        echo -e "Server:  ${GREEN}Running${NC} (PID: $SERVER_PID)"
        echo "         http://localhost:4000"
        echo "         ws://localhost:4000/stream"
    else
        echo -e "Server:  ${RED}Stopped${NC}"
    fi

    echo ""

    # Client status
    if [ -f "$CLIENT_PID_FILE" ] && kill -0 "$(cat "$CLIENT_PID_FILE")" 2>/dev/null; then
        CLIENT_PID=$(cat "$CLIENT_PID_FILE")
        echo -e "Client:  ${GREEN}Running${NC} (PID: $CLIENT_PID)"
        echo "         http://localhost:5173"
    else
        echo -e "Client:  ${RED}Stopped${NC}"
    fi

    echo ""
}

case "${1:-}" in
    start)
        check_dependencies
        start_server
        start_client
        echo ""
        log_info "Dashboard available at http://localhost:5173"
        ;;
    stop)
        stop_client
        stop_server
        ;;
    restart)
        stop_client
        stop_server
        sleep 1
        check_dependencies
        start_server
        start_client
        echo ""
        log_info "Dashboard available at http://localhost:5173"
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
