import os

from image_enhancer import ImageEnhancer, read_settings_file

settings_file = input("Enter settings file: ")
folder_path = input("Enter folder path: ")

settings_file_path = os.path.join('/cloud/copy_script', settings_file)

enhancer = ImageEnhancer(read_settings_file(settings_file_path))
enhancer.enhance_folder(folder_path)
enhancer.chown_folder(folder_path)
enhancer.index_folder(folder_path)

