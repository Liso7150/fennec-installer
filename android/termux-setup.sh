#!/data/data/com.termux/files/usr/bin/bash
# Fennec Termux bootstrap (Android). Runs the core-supervised PWA/API on the phone
# itself, with an optional Rust auxiliary/chat service and the Fennec engine.
set -e
ROOT="${FENNEC_ROOT:-$HOME/Fennec}"

pkg update -y
# rust supplies cargo, which builds the native Fennec engine and the optional Rust
# auxiliary/chat service on the phone; clang/cmake cover the C dependencies.
pkg install -y python git clang make cmake rust binutils curl termux-tools

if [ ! -d "$HOME/fennec-installer" ]; then
  git clone https://github.com/Liso7150/fennec-installer "$HOME/fennec-installer"
fi

cd "$HOME/fennec-installer"
echo "Installing the phone-local core and PWA under $ROOT ..."
python install.py --install --features mobile --yes --root "$ROOT"

cat > "$ROOT/open-fennec.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
# Start the core-supervised PWA/API, optionally the Rust auxiliary/chat service,
# and the local engine (when a model is present); stop everything on Ctrl+C.
set -e
ROOT="$ROOT"
CORE_AGENT="\$PREFIX/bin/fennec-agent"
RUST_AGENT="\$ROOT/suite/fennec-coding-agent/target/release/fennec-agent"
ENGINE="\$ROOT/engine/target/release/fennec"
termux-wake-lock
CORE_AGENT_PID=""
RUST_AGENT_PID=""
ENGINE_PID=""
cleanup() {
  # Both agent executables are named fennec-agent; only their own PIDs are safe
  # process identities here. Never kill that basename across the whole device.
  if [ -n "\$RUST_AGENT_PID" ]; then
    kill "\$RUST_AGENT_PID" 2>/dev/null || true
    wait "\$RUST_AGENT_PID" 2>/dev/null || true
  fi
  if [ -n "\$CORE_AGENT_PID" ]; then
    kill "\$CORE_AGENT_PID" 2>/dev/null || true
    wait "\$CORE_AGENT_PID" 2>/dev/null || true
  fi
  if [ -n "\$ENGINE_PID" ]; then
    kill "\$ENGINE_PID" 2>/dev/null || true
    wait "\$ENGINE_PID" 2>/dev/null || true
  fi
  termux-wake-unlock
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [ ! -x "\$CORE_AGENT" ]; then
  echo "The installed core launcher is missing: \$CORE_AGENT" >&2
  exit 1
fi
"\$CORE_AGENT" serve --host 127.0.0.1 --port 8787 &
CORE_AGENT_PID=\$!
if [ -x "\$RUST_AGENT" ]; then
  FENNEC_AGENT_ADDR=127.0.0.1:8788 "\$RUST_AGENT" &
  RUST_AGENT_PID=\$!
else
  echo "Optional Rust auxiliary/chat service is not built; core continues without it."
fi
if [ -x "\$ENGINE" ] && [ -n "\$FENNEC_MODEL" ] && [ -d "\$FENNEC_MODEL" ] && [ -f "\$FENNEC_MODEL/config.json" ]; then
  "\$ENGINE" serve --auto-tier --model "\$FENNEC_MODEL" --host 127.0.0.1 --port 8184 &
  ENGINE_PID=\$!
else
  echo "No servable model selected: FENNEC_MODEL must be a directory holding config.json and *.safetensors."
  echo "The engine converts nothing, so a packed checkpoint goes through the core (fennec-convert) first."
  echo "The PWA runs, but inference needs an engine on 127.0.0.1:8184."
fi
supervised_capabilities() {
  python -c 'import json, sys
required = {"supervised-agent", "tool-execution", "per-call-approvals", "agent-polling"}
try:
    payload = json.load(sys.stdin)
    features = payload.get("features")
except (ValueError, AttributeError):
    sys.exit(1)
if not isinstance(features, list) or not all(isinstance(feature, str) for feature in features):
    sys.exit(1)
sys.exit(0 if required.issubset(features) else 1)'
}
READY=""
for _ in \$(seq 1 150); do
  if CAPABILITIES="\$(curl -fsS --max-time 2 -H "X-Fennec-Client: 1" "http://127.0.0.1:8787/api/capabilities" 2>/dev/null)" &&
     printf '%s' "\$CAPABILITIES" | supervised_capabilities; then
    READY=1
    break
  fi
  if ! kill -0 "\$CORE_AGENT_PID" 2>/dev/null; then
    echo "The core service exited before advertising supervised coding capabilities." >&2
    exit 1
  fi
  sleep 0.2
done
if [ -z "\$READY" ]; then
  echo "Core did not advertise supervised-agent, tool-execution, per-call-approvals and agent-polling at GET /api/capabilities on 127.0.0.1:8787; refusing a chat-only fallback." >&2
  exit 1
fi
termux-open-url "http://127.0.0.1:8787/"
echo "Fennec core-supervised PWA/API is running at http://127.0.0.1:8787/ - press Ctrl+C here to stop it."
echo "The optional Rust auxiliary/chat service uses http://127.0.0.1:8788/; the engine stays on 127.0.0.1:8184."
wait "\$CORE_AGENT_PID"
EOF
chmod +x "$ROOT/open-fennec.sh"
ln -sf "$ROOT/open-fennec.sh" "$PREFIX/bin/fennec-open"

echo
echo "Done. Start Fennec with:  fennec-open"
echo "All files stay under $ROOT; set FENNEC_MODEL to a local model dir to enable on-device inference."
echo "On-device inference needs a compatible small model in $ROOT/models and a Fennec build (cargo build --release in $ROOT/engine)."
echo "The 35B model does not fit on a phone."