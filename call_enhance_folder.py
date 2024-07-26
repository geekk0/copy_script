import os

from enhance_caller import EnhanceCaller, read_settings_file

settings_file = input("Enter settings file: ")
folder_path = input("Enter folder path: ")
folder_path = folder_path.encode('utf-8').decode('utf-8', errors='ignore')

settings_file_path = os.path.join('/cloud/copy_script', settings_file)

enhancer = EnhanceCaller(read_settings_file(settings_file_path))

enhancer.add_to_ai_queue(folder_path)

