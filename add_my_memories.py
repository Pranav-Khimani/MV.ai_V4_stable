from pathlib import Path

from memory.memory_manager import MemoryManager


def main() -> None:
    project_root = Path(__file__).resolve().parent

    database_path = (
        project_root
        / "data"
        / "mv_memory.db"
    )

    print(
        f"Using database: {database_path}"
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

    
    memory.remember(
        key="main project",
        value="MV.AI V3",
        category="project",
        importance=10,
    )

    memory.remember(
        key="preferred code editor",
        value="Visual Studio Code",
        category="preference",
        importance=8,
    )

    print()
    print(memory.get_memory_context())

    memory.end_session()

    print()
    print("Memories added successfully.")


if __name__ == "__main__":
    main()