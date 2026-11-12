#!/usr/bin/env bash
# ccswitch installer
# Local-only installer. No network or update fallback.
set -euo pipefail

PREFIX="${PREFIX:-$HOME/.local/bin}"
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

command -v python3 >/dev/null 2>&1 || { echo "python3 is required"; exit 1; }

mkdir -p "$PREFIX"

[ -f "$SOURCE_DIR/bin/ccswitch" ] || { echo "local source is missing; refusing to download anything" >&2; exit 1; }
bash -n "$SOURCE_DIR/bin/ccswitch"
install -m 755 "$SOURCE_DIR/bin/ccswitch" "$PREFIX/ccswitch"

echo "installed -> $PREFIX/ccswitch"

case ":$PATH:" in
  *":$PREFIX:"*) ;;
  *)
    echo
    echo "$PREFIX is not on your PATH. Add it:"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
    ;;
esac

cat <<'EOF'

Optional shell completion:
  # zsh
  mkdir -p ~/.zfunc && ccswitch completion zsh > ~/.zfunc/_ccswitch
  echo 'fpath=(~/.zfunc $fpath); autoload -Uz compinit && compinit' >> ~/.zshrc
  # bash
  ccswitch completion bash >> ~/.bashrc

Get started:
  ccswitch login work
  ccswitch login personal
  ccswitch list
EOF
