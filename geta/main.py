from pathlib import Path

from . import workers


def main():
    location = Path.cwd()

    raw_title = input("Task description: \n")
    if not raw_title:
        return

    standardized_title = workers.standardize_string(raw_title)

    folder_name = workers.build_folder_name(standardized_title)

    created_folder = workers.create_folder(location, folder_name)

    created_file = workers.create_md_file(created_folder, standardized_title)

    workers.sign_md_file(created_file, created_folder)