"""Business Rules Platform core package."""

__version__ = "0.1.0"


def main() -> None:
    """Run the BRP orchestration CLI."""
    from brp.cli import app

    app()
