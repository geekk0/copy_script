import os
import argparse
from image_enhancer import ImageEnhancer, read_settings_file


def parse_args():
    parser = argparse.ArgumentParser(description="Image Enhancer")
    parser.add_argument("settings_file", nargs="?", help="Path to the settings file")
    parser.add_argument("folder_path", nargs="?", help="Path to the folder containing images")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.settings_file and args.folder_path:
        settings_file = os.path.join('/cloud/copy_script', args.settings_file)
        folder_path = args.folder_path
    else:
        settings_file = input("Enter settings file: ")
        folder_path = input("Enter folder path: ")
        folder_path = folder_path.encode('utf-8').decode('utf-8', errors='ignore')

        settings_file = os.path.join('/cloud/copy_script', settings_file)

    enhancer = ImageEnhancer(read_settings_file(settings_file))
    new_folder = enhancer.enhance_folder(folder_path)
    enhancer.chown_folder(new_folder)
    enhancer.index_folder(new_folder)


if __name__ == "__main__":
    main()
