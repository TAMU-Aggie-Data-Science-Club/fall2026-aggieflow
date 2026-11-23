"""Checks on the Dockerfile and .dockerignore (#144). Docker itself isn't needed."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_image_leaves_out_keys_and_data():
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").split()
    assert {"**/.env", "**/.env.*", "data/", ".git/"} <= set(ignored)


def test_the_image_builds_the_ui_for_the_same_address_and_listens_on_port():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "VITE_API_URL=/ npm run build" in dockerfile  # the UI calls /chat on the API's own address
    assert "COPY --from=web /web/dist web/dist" in dockerfile  # where api/main.py looks for it
    assert "uv sync --locked --no-dev" in dockerfile
    assert "${PORT:-8000}" in dockerfile  # hosts set PORT
