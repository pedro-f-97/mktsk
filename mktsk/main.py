from pathlib import Path

from . import workers


def main() -> int:
    location = Path.cwd()

    raw_title = input("Task: \n")
    if not raw_title.strip():
        print("Error: invalid task description.")
        return 1

    standardized_title = workers.standardize_string(raw_title)
    if not standardized_title.strip():
        print("Error: invalid task description.")
        return 1

    folder_name = workers.build_folder_name(standardized_title)

    try:
        created_folder = workers.create_folder(location, folder_name)
        created_file = workers.create_md_file(created_folder, standardized_title)
        workers.sign_md_file(created_file, folder_name)
    except (OSError, ValueError) as error:
        print(f"Error: {error}")
        return 1

    print(f"Created: {folder_name}")
    return 0

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())