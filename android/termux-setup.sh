#!/data/data/com.termux/files/usr/bin/bash
# Fennec Termux bootstrap (Android). Runs the Rust coding-agent backend and PWA on
# the phone itself; the Fennec engine is started here when a model is present.
set -e
ROOT="${FENNEC_ROOT:-$HOME/Fennec}"

pkg update -y
# rust supplies cargo, which builds the native Fennec engine and the Rust
# coding-agent backend on the phone; clang/cmake cover the C dependencies.
pkg install -y python git clang make cmake rust binutils curl termux-tools

if [ ! -d "$HOME/fennec-installer" ]; then
  git clone https://github.com/Liso7150/fennec-installer "$HOME/fennec-installer"
fi

cd "$HOME/fennec-installer"
echo "Installing the phone-local core and PWA under $ROOT ..."
python install.py --install --features mobile --yes --root "$ROOT"

cat > "$ROOT/open-fennec.sh" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
# Start the local Fennec engine (when a model is present) and the Rust
# coding-agent backend, open the PWA, stop everything on Ctrl+C.
set -e
ROOT="$ROOT"
AGENT="\$ROOT/suite/fennec-coding-agent/target/release/fennec-agent"
ENGINE="\$ROOT/engine/target/release/fennec"
termux-wake-lock
ENGINE_PID=""
if [ -x "\$ENGINE" ] && [ -n "\$FENNEC_MODEL" ] && [ -d "\$FENNEC_MODEL" ] && [ -f "\$FENNEC_MODEL/config.json" ]; then
  "\$ENGINE" serve --auto-tier --model "\$FENNEC_MODEL" --host 127.0.0.1 --port 8184 &
  ENGINE_PID=\$!
else
  echo "No servable model selected: FENNEC_MODEL must be a directory holding config.json and *.safetensors."
  echo "The engine converts nothing, so a packed checkpoint goes through the core (fennec-convert) first."
  echo "The PWA runs, but inference needs an engine on 127.0.0.1:8184."
fi
"\$AGENT" &
AGENT_PID=\$!
cleanup() {
  kill "\$AGENT_PID" 2>/dev/null || true
  [ -n "\$ENGINE_PID" ] && kill "\$ENGINE_PID" 2>/dev/null || true
  termux-wake-unlock
}
trap cleanup EXIT INT TERM
# The Rust agent binds 8787 and falls back to 8788 when 8787 is occupied.
PORT=""
for _ in \$(seq 1 150); do
  for candidate in 8787 8788; do
    if curl -fsS -H "X-Fennec-Client: 1" "http://127.0.0.1:\$candidate/api/health" >/dev/null 2>&1; then
      PORT="\$candidate"
      break 2
    fi
  done
  sleep 0.2
done
if [ -z "\$PORT" ]; then
  echo "The coding-agent backend did not become healthy on 8787/8788." >&2
  exit 1
fi
termux-open-url "http://127.0.0.1:\$PORT/"
echo "Fennec is running at http://127.0.0.1:\$PORT/ - press Ctrl+C here to stop it."
wait "\$AGENT_PID"
EOF
chmod +x "$ROOT/open-fennec.sh"
ln -sf "$ROOT/open-fennec.sh" "$PREFIX/bin/fennec-open"

echo
echo "Done. Start Fennec with:  fennec-open"
echo "All files stay under $ROOT; set FENNEC_MODEL to a local model dir to enable on-device inference."
echo "On-device inference needs a compatible small model in $ROOT/models and a Fennec build (cargo build --release in $ROOT/engine)."
echo "The 35B model does not fit on a phone."