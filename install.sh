#!/bin/sh
set -e

REPO="https://github.com/sacharias/gh-trending"

main() {
    if ! command -v uv >/dev/null 2>&1; then
        echo "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi

    echo "Installing gh-trending..."
    uv tool install "gh-trending @ git+${REPO}"

    if command -v gh-trending >/dev/null 2>&1; then
        echo ""
        echo "Installed! Run 'gh-trending' to get started."
    else
        echo ""
        echo "Installed! You may need to add ~/.local/bin to your PATH:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

main
