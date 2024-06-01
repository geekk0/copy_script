import os

from image_enhancer import ImageEnhancer, read_settings_file

settings_file = input("Enter settings file: ")
folder_path = input("Enter folder path: ")
folder_path = folder_path.encode('utf-8').decode('utf-8', errors='ignore')


settings_file_path = os.path.join('/cloud/copy_script', settings_file)

enhancer = ImageEnhancer(read_settings_file(settings_file_path))
enhancer.enhance_folder(folder_path)
new_folder = enhancer.rename_folder(folder_path)
enhancer.chown_folder(new_folder)
enhancer.index_folder(new_folder)

