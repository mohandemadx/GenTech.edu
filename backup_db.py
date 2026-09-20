import os
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RETENTION = 14


class BackupError(RuntimeError):
    """Raised when a database backup cannot be created safely."""


def _database_path(database_url=None):
    database_url = database_url or os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'grades.db'}")
    if not database_url.startswith("sqlite:///"):
        raise BackupError("Automatic file backups support SQLite only.")
    database_path = database_url[len("sqlite:///"):]
    if database_path == ":memory:":
        raise BackupError("Automatic file backups are unavailable for an in-memory database.")
    return Path(database_path)


def create_backup(database_url=None, backup_dir=None, retention=DEFAULT_RETENTION):
    source_path = _database_path(database_url)
    if not source_path.exists():
        raise BackupError(f"Database file does not exist: {source_path}")

    destination_dir = Path(backup_dir) if backup_dir else BASE_DIR / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination_path = destination_dir / f"grades-{timestamp}.db"

    try:
        source = sqlite3.connect(str(source_path))
        destination = sqlite3.connect(str(destination_path))
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
    except sqlite3.Error as error:
        if destination_path.exists():
            destination_path.unlink()
        raise BackupError(f"Database backup failed: {error}") from error

    backups = sorted(destination_dir.glob("grades-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old_backup in backups[retention:]:
        old_backup.unlink()
    return destination_path


if __name__ == "__main__":
    backup = create_backup()
    print(f"Created database backup: {backup}")
