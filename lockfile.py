import os
import time
import json


class LockFileWrapper:
    def __init__(self, lock_file_path):
        self.lock_file_path = lock_file_path

    def __enter__(self):
        while not self.acquire_lock():
            time.sleep(0.1)  # Wait for 0.1 seconds before trying again

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_lock()

    def acquire_lock(self):
        try:
            # Attempt to acquire the lock by creating the lock file
            with open(self.lock_file_path, 'x') as lock_file:
                return True
        except FileExistsError:
            # Lock file already exists, so another process has the lock
            return False

    def release_lock(self):
        try:
            # Remove the lock file to release the lock
            os.remove(self.lock_file_path)
        except FileNotFoundError:
            # Lock file was already removed, so nothing to do
            pass


def write_to_log(message, log_file_path, level, logger):
    lock_file_path = f'{log_file_path}.lock'
    with LockFileWrapper(lock_file_path):
        logger.log(level, message)


def write_to_common_file(message, common_file_path):
    lock_file_path = f'{common_file_path}.lock'
    with LockFileWrapper(lock_file_path):
        with open(common_file_path, 'w') as common_file:
            json.dump(message, common_file)
            return lock_file_path