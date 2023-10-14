"""
macro_recorder_ui.py

Wraps macro_recorder with a graphical interface, that allows for:
- Picking the 'config' and 'device' from a list instead of typing them in.
- Entering a prefix for the 'action' name instead of defaulting to 'click_XX'.
- Recording multiple 'action' chains without starting and stopping everything.

Like macro_recorder, outputs a 'config' folder of images and a json file.

Needs to be run as a module "python -m tools.macro_recorder_ui"
"""

import argparse
import tkinter as tk
from queue import SimpleQueue, Empty
import threading
from typing import Optional

from fbmr.devices import all_device_constructors, WindowsAppDeviceConfig, WindowsAndroidDeviceConfig
from fbmr.editor import all_config_names, ConfigUtil

from tools.macro_recorder import record_macro, EXIT_COMMAND


class MacroRecorderUI:
    def __init__(self):
        self.command_queue = SimpleQueue()
        self.feedback_queue = SimpleQueue()
        self.thread = None  # type: Optional[threading.Thread]

    # noinspection PyAttributeOutsideInit
    def run(self):
        self.window = tk.Tk()
        self.window.title("Macro Recorder UI")

        # Row 1
        self.device_label = tk.Label(self.window, text="Device:")
        self.device_label.grid(row=0, column=0)
        devices_dict = all_device_constructors(allowed_types=[
            WindowsAndroidDeviceConfig.name(),
            WindowsAppDeviceConfig.name(),
        ])
        self.device_options = [x for x in devices_dict.keys()]
        self.device_var = tk.StringVar(self.window)
        self.device_var.set(self.device_options[0])
        self.device_dropdown = tk.OptionMenu(self.window, self.device_var, *self.device_options)
        self.device_dropdown.grid(row=0, column=1)

        # Row 2
        self.config_label = tk.Label(self.window, text="Config:")
        self.config_label.grid(row=1, column=0)
        self.config_options = [x for x in all_config_names()]
        self.config_var = tk.StringVar(self.window)
        self.config_var.set(self.config_options[0])
        self.config_dropdown = tk.OptionMenu(self.window, self.config_var, *self.config_options)
        self.config_dropdown.grid(row=1, column=1)
        self.new_config_button = tk.Button(self.window, text="New Config", command=self.create_new_config)
        self.new_config_button.grid(row=1, column=2)

        # Row 3
        self.start_recording_button = tk.Button(self.window, text="Start Recording", command=self.start_recording)
        self.start_recording_button.grid(row=2, column=0)
        self.stop_recording_button = tk.Button(self.window, text="Stop Recording", command=self.stop_recording)
        self.stop_recording_button.grid(row=2, column=1)

        # Row 4
        self.action_prefix_label = tk.Label(self.window, text="Action Prefix:")
        self.action_prefix_label.grid(row=3, column=0)
        self.action_prefix_entry = tk.Entry(self.window)
        self.action_prefix_entry.grid(row=3, column=1)

        self.window.mainloop()

    def create_new_config(self):
        new_config_window = tk.Toplevel(self.window)

        # Row 1
        new_config_label = tk.Label(new_config_window, text="New Config Name:")
        new_config_label.grid(row=0, column=0)
        new_config_entry = tk.Entry(new_config_window)
        new_config_entry.grid(row=0, column=1)

        # Row 2
        create_button = tk.Button(
            new_config_window,
            text="Create",
            command=lambda: self.add_new_config(new_config_entry.get(), new_config_window))
        create_button.grid(row=1, column=1)

    def add_new_config(self, config_name, window):
        ConfigUtil.write_new_json(config_name)

        self.config_options.clear()
        self.config_options.extend(all_config_names())
        self.config_var.set(config_name)
        self.config_dropdown['menu'].delete(0, 'end')
        for option in self.config_options:
            self.config_dropdown['menu'].add_command(label=option, command=tk._setit(self.config_var, option))
        window.destroy()

    def start_recording(self):
        if self.thread and self.thread.is_alive():
            return

        self.thread = threading.Thread(
            target=record_macro,
            args=(self.config_var.get(), self.device_var.get(), self.action_prefix_entry.get(),
                  self.command_queue, self.feedback_queue))
        self.thread.daemon = True
        self.thread.start()

    def stop_recording(self):
        self.command_queue.put(EXIT_COMMAND)


def launch_macro_recorder_ui():
    ui = MacroRecorderUI()
    ui.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    launch_macro_recorder_ui()
