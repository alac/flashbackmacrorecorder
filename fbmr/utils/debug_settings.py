import os
import time
import datetime

from fbmr.utils.settings import settings


THIS_FILES_FOLDER = os.path.dirname(os.path.realpath(__file__))
DEBUG_FOLDER = os.path.join(THIS_FILES_FOLDER, "..", "..", "debug")
LOGS_FOLDER = os.path.join(THIS_FILES_FOLDER, "..", "..", "logs")


def delete_stale_files_in_folder(folder_path, expiration_duration):
    if os.path.exists(folder_path):
        current_time = time.time()

        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    file_modification_time = os.path.getmtime(file_path)
                    if (current_time - file_modification_time) > expiration_duration:
                        os.unlink(file_path)
    os.makedirs(folder_path, exist_ok=True)


class DebugSettings:
    def __init__(self):
        self.debug_folder = DEBUG_FOLDER
        self.log_folder = LOGS_FOLDER

        delete_stale_files_in_folder(self.debug_folder, settings.get_debug_image_expire_time())
        delete_stale_files_in_folder(self.log_folder, settings.get_debug_log_expire_time())

        self.save_detect_subimage_images = False
        self.log_detect_subimage = False
        self.detect_subimages_logger = lambda x: print(x)

        self.action_logger = lambda x: print("  ", x)
        self.condition_logger = lambda x: print("    ", x)

        self.timeout_timestamp = 0
        self.timeout_duration = 0

    def save_image_with_timestamp(self, image, suffix_filename):
        timestamp = datetime.datetime.now().strftime("%Y %B %d %A %I-%M-%S%p")
        debug_image_name = os.path.join(debug_settings.debug_folder, f"{timestamp} - {suffix_filename}.png")
        image.save(debug_image_name)

    def set_timeout_seconds(self, seconds):
        self.timeout_timestamp = time.time()
        self.timeout_duration = seconds

    def check_timeout(self):
        if self.timeout_timestamp != 0 and time.time() > (self.timeout_timestamp + self.timeout_duration):
            raise GlobalTimeoutError(f"Timeout Exceeded {self.timeout_duration}")

    def clear_timeout(self):
        self.timeout_timestamp = 0
        self.timeout_duration = 0


debug_settings = DebugSettings()


class GlobalTimeoutError(Exception):
    pass

