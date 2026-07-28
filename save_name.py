from pathlib import Path

from memory.memory_manager import MemoryManager


project_root = Path(__file__).resolve().parent

database_path = (
    project_root
    / "data"
    / "mv_memory.db"
)

memory = MemoryManager(
    database_path=str(database_path)
)

memory.remember(
    key="name",
    value="Pranav",
    category="personal",
    importance=10,
)
memory.remember(
    key="nickname",
    value="Multiverse",
    category="personal",
    importance=12,
)
print(memory.get_memory_context())

memory.end_session()