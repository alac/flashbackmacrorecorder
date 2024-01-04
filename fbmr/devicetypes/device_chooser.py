import subprocess
import sys
import time
import tkinter

from fbmr.devicetypes.windows_app_device import WindowManager


class ADBInterface:
    """ADBDevice communicates with a running Android device."""

    @classmethod
    def devices(cls):
        return [
            str(dev.split(b"\t")[0])[2:-1]
            for dev in subprocess.check_output(["adb", "devices"]).splitlines()
            if dev.endswith(b"\tdevice")
        ]

    @classmethod
    def get_screen_resolution(cls, serial):
        device_info = subprocess.check_output(
            ["adb", "-s", f"{serial}", "shell", "wm size"]
        ).splitlines()
        """
        Expected:
        Physical size: 1440x3040
        Override size: 1080x2280
        """
        physical_size = None
        override_size = None
        for size in device_info:
            if b": " in size:
                wxh_str = size.split(b": ")[1].split(b"x")
                w, h = int(wxh_str[0]), int(wxh_str[1])

                if physical_size is None:
                    physical_size = (w, h)
                if override_size is None:
                    override_size = (w, h)

                if size.startswith(b"Physical"):
                    physical_size = (w, h)
                if size.startswith(b"Override"):
                    override_size = (w, h)
        return {"physical_size": physical_size, "override_size": override_size}

    @classmethod
    def run_tcpip(cls, serial):
        subprocess.check_output(["adb", "-s", f"{serial}", "tcpip", "5555"])


def exit_app():
    # cleanup_processes()
    sys.exit(1)


def pick_android_device(window_title, completion_callback):
    window = tkinter.Tk()
    window.title(window_title)

    window.columnconfigure(0, weight=1, minsize=100)
    window.columnconfigure(1, weight=4, minsize=500)

    def reload_window():
        for widget in window.winfo_children():
            widget.destroy()

        load_window()

    def load_window():
        row = 0

        run_button = tkinter.Button(window, text="Reload", command=reload_window)
        run_button.grid(row=row, column=0, sticky="w")

        row += 1

        attached_devices = ADBInterface.devices()

        if not attached_devices:
            run_button = tkinter.Button(
                window, text="Error: No device detected", command=exit_app
            )
            run_button.grid(row=row, column=0, sticky="w")

            return

        # append true resolutions
        descriptive_devices = []
        for device in attached_devices:
            size = ADBInterface.get_screen_resolution(device)["override_size"]
            descriptive_devices.append(f"{device} {size}")

        tkinter.Label(window, text="Device").grid(row=row, sticky="w")
        device_variable = tkinter.StringVar(window)
        if attached_devices:
            device_variable.set(descriptive_devices[0])  # default value
        device_dropdown = tkinter.OptionMenu(
            window, device_variable, *descriptive_devices
        )
        device_dropdown.grid(row=row, column=1, sticky="nesw")

        row += 1

        def start():
            serial_raw = str(device_variable.get()).split(" ")[0]
            window.destroy()
            completion_callback(serial_raw)

        def run_tcpip():
            serial_raw = str(device_variable.get()).split(" ")[0]
            ADBInterface.run_tcpip(serial_raw)
            time.sleep(5)  # give device time to connect
            reload_window()

        run_button = tkinter.Button(window, text="Start", command=start)
        run_button.grid(row=row, column=0, sticky="w")
        run_button = tkinter.Button(window, text="Enable Wifi", command=run_tcpip)
        run_button.grid(row=row, column=1, sticky="w")

        window.protocol("WM_DELETE_WINDOW", exit_app)
        window.mainloop()

    load_window()


def pick_application_window(window_title, completion_callback):
    window = tkinter.Tk()
    window.title(window_title)

    window.columnconfigure(0, weight=1, minsize=100)
    window.columnconfigure(1, weight=4, minsize=500)

    def reload_window():
        for widget in window.winfo_children():
            widget.destroy()

        load_window()

    def load_window():
        row = 0

        run_button = tkinter.Button(window, text="Reload", command=reload_window)
        run_button.grid(row=row, column=0, sticky="w")

        row += 1

        window_manager = WindowManager()
        window_titles = window_manager.all_window_titles()

        if not window_titles:
            run_button = tkinter.Button(
                window, text="Error: Failed to detect windows", command=exit_app
            )
            run_button.grid(row=row, column=0, sticky="w")

            return

        tkinter.Label(window, text="Device").grid(row=row, sticky="w")
        selected_title_variable = tkinter.StringVar(window)
        if window_titles:
            selected_title_variable.set(window_titles[0])  # default value
        device_dropdown = tkinter.OptionMenu(
            window, selected_title_variable, *window_titles
        )
        device_dropdown.grid(row=row, column=1, sticky="nesw")

        row += 1

        def start():
            selected_title = str(selected_title_variable.get())
            window.destroy()
            completion_callback(selected_title)

        run_button = tkinter.Button(window, text="Start", command=start)
        run_button.grid(row=row, column=0, sticky="w")

        window.protocol("WM_DELETE_WINDOW", exit_app)
        window.mainloop()

    load_window()
