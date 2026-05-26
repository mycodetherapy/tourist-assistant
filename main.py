"""CLI entry."""

from cli.app import main
from config.settings import ensure_env

if __name__ == "__main__":
    ensure_env()
    main()
