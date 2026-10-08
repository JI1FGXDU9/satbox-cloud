#!/usr/bin/env bash
# Linux/Xserver: run with bash notification_workers.sh start|stop|status|restart
set -u
umask 077
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || exit 1
cd -- "$project_dir" || exit 1
mkdir -p logs || exit 1
command -v flock >/dev/null || { echo 'flock is required.' >&2; exit 1; }
exec 9>logs/workers.lock
flock -n 9 || { echo 'Another worker management command is running.' >&2; exit 1; }

matches_worker() {
    local pid="$1" script="$2" worker_args worker_cwd
    [[ "$pid" =~ ^[1-9][0-9]*$ ]] || return 1
    [[ -r "/proc/$pid/cmdline" ]] || return 1
    # /proc may disappear between the readability check and the read on exit.
    # Capture once, treating that normal race as "not running".
    worker_args=$( { tr '\0' '\n' < "/proc/$pid/cmdline"; } 2>/dev/null) || return 1
    if printf '%s\n' "$worker_args" | grep -Fxq -- "$project_dir/$script"; then
        return 0
    fi
    # Also recognize workers started by the earlier relative-path nohup command.
    worker_cwd=$(readlink -- "/proc/$pid/cwd" 2>/dev/null) || return 1
    [[ "$worker_cwd" == "$project_dir" ]] || return 1
    printf '%s\n' "$worker_args" | grep -Fxq -- "$script"
}

start_worker() {
    local name="$1" script="$2" pid=''
    if [[ -f "logs/$name.pid" ]]; then
        read -r pid < "logs/$name.pid" || true
        if matches_worker "$pid" "$script"; then
            echo "$name already running (PID $pid)"
            return 0
        fi
    fi
    [[ -x .venv/bin/python && -f "$script" ]] || {
        echo "Missing .venv/bin/python or $script" >&2; return 1;
    }
    # Close the management lock in the child; otherwise the daemon retains it.
    nohup env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
        "$project_dir/.venv/bin/python" -u "$project_dir/$script" --loop \
        >> "logs/$name.log" 2>&1 < /dev/null 9>&- &
    pid=$!
    printf '%s\n' "$pid" > "logs/$name.pid"
    sleep 1
    if matches_worker "$pid" "$script"; then
        echo "$name started (PID $pid)"
    else
        rm -f -- "logs/$name.pid"
        echo "$name failed to start. Check logs/$name.log" >&2
        return 1
    fi
}

stop_worker() {
    local name="$1" script="$2" pid='' attempt
    [[ -f "logs/$name.pid" ]] || { echo "$name stopped"; return 0; }
    read -r pid < "logs/$name.pid" || true
    if matches_worker "$pid" "$script"; then
        kill -TERM "$pid" || return 1
        for attempt in {1..25}; do
            matches_worker "$pid" "$script" || break
            sleep 0.2
        done
        if matches_worker "$pid" "$script"; then
            echo "$name is still stopping (PID $pid); try status shortly." >&2
            return 1
        fi
    fi
    rm -f -- "logs/$name.pid"
    echo "$name stopped"
}

status_worker() {
    local name="$1" script="$2" pid=''
    [[ ! -f "logs/$name.pid" ]] || read -r pid < "logs/$name.pid" || true
    if matches_worker "$pid" "$script"; then
        echo "$name running (PID $pid)"
    else
        echo "$name stopped"
        return 1
    fi
}

start_all() {
    local result=0
    start_worker prepare prepare_notifications.py || result=1
    start_worker send send_notifications.py || result=1
    return "$result"
}
stop_all() {
    local result=0
    stop_worker send send_notifications.py || result=1
    stop_worker prepare prepare_notifications.py || result=1
    return "$result"
}
case "${1:-status}" in
    start) start_all ;;
    stop) stop_all ;;
    restart) stop_all && start_all ;;
    status)
        result=0
        status_worker prepare prepare_notifications.py || result=1
        status_worker send send_notifications.py || result=1
        exit "$result"
        ;;
    *) echo 'Usage: bash notification_workers.sh start|stop|status|restart' >&2; exit 2 ;;
esac
