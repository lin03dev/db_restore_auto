import shutil
from pathlib import Path
from typing import Optional


def find_pg_tool(tool_name: str, configured_path: Optional[str] = None) -> Optional[str]:
    """Find PostgreSQL command-line tools on PATH or common Windows installs."""
    candidates = []

    if configured_path:
        candidates.append(Path(configured_path))

    path_match = shutil.which(configured_path or tool_name)
    if path_match:
        return path_match

    path_match = shutil.which(tool_name)
    if path_match:
        return path_match

    program_files = Path("C:/Program Files/PostgreSQL")
    if program_files.exists():
        candidates.extend(program_files.glob(f"*/bin/{tool_name}.exe"))
        candidates.extend(program_files.glob(f"*/pgAdmin 4/runtime/{tool_name}.exe"))

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return None


def pg_tool_or_raise(tool_name: str, configured_path: Optional[str] = None) -> str:
    tool_path = find_pg_tool(tool_name, configured_path)
    if tool_path:
        return tool_path

    raise FileNotFoundError(
        f"Could not find {tool_name}. Install PostgreSQL command-line tools or add "
        r"C:\Program Files\PostgreSQL\<version>\bin to PATH."
    )
