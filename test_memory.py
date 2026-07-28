from memory.memory_manager import MemoryManager


def print_section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def main() -> None:
    memory = MemoryManager(
        database_path="data/test_memory.db"
    )

    print_section("REMEMBERING INFORMATION")

    name_memory = memory.remember(
        key="name",
        value="Pranav",
        category="personal",
        importance=10,
    )

    project_memory = memory.remember(
        key="main project",
        value="MV.AI V3",
        category="project",
        importance=9,
    )

    folder_memory = memory.remember(
        key="project folder",
        value=r"D:\Projects\MV_AI_V3",
        category="folder",
        importance=9,
    )

    print(name_memory)
    print(project_memory)
    print(folder_memory)

    print_section("RECALLING NAME")

    recalled_name = memory.recall(
        key="name",
        category="personal",
    )

    print(recalled_name)

    print_section("SEARCHING FOR PROJECT")

    search_results = memory.search(
        query="project"
    )

    for result in search_results:
        print(
            result["category"],
            result["memory_key"],
            "=",
            result["memory_value"],
        )

    print_section("CONVERSATION HISTORY")

    memory.add_conversation_message(
        role="user",
        content="Remember that my name is Pranav.",
    )

    memory.add_conversation_message(
        role="assistant",
        content="I will remember that your name is Pranav.",
    )

    history = memory.get_conversation_history()

    for message in history:
        print(
            f"{message['role']}: "
            f"{message['content']}"
        )

    print_section("COMMAND HISTORY")

    memory.log_command(
        command="Open YouTube",
        success=True,
        response="YouTube opened successfully.",
    )

    commands = memory.get_recent_commands()

    for command in commands:
        print(
            command["command"],
            "| success:",
            bool(command["success"]),
        )

    print_section("GEMINI MEMORY CONTEXT")

    print(
        memory.get_memory_context()
    )

    print_section("FORGETTING A MEMORY")

    forgotten = memory.forget(
        key="project folder",
        category="folder",
    )

    print("Forgotten:", forgotten)

    missing_memory = memory.recall(
        key="project folder",
        category="folder",
    )

    print(
        "Recall after forgetting:",
        missing_memory,
    )

    memory.end_session()

    print_section("MEMORY TEST PASSED")


if __name__ == "__main__":
    main()