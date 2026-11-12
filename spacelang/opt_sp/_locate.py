from pathlib import Path


def static_dir() -> Path:
    directory = Path(__file__).parent / "static"
    if not directory.is_dir():
        raise RuntimeError(
            "OPT_SP static files are missing; reinstall with "
            "`pip install --force-reinstall spacelanguage`."
        )
    return directory


__all__ = ["static_dir"]
