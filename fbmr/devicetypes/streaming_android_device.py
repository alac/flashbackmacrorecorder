from typing import Optional
from PIL import Image
import scrcpy
import threading
from queue import LifoQueue, Empty
import cv2

from fbmr.devicetypes import adb_alt_device
from fbmr.utils.settings import settings

EVENT_SCREEN_OFF = "SCREEN_OFF"
EVENT_SCREEN_ON = "SCREEN_ON"
SCRCPY_DEVICE_KILL_THREAD = "SCRCPY_DEVICE_KILL_THREAD"

image_condition = threading.Condition()
last_image = None


class StreamingAndroidDevice(adb_alt_device.ADBAltDevice):
    """
    StreamingAndroidDevice is an improvement on ADBDevice:
    - Use adb for interaction that doesn't interfere with the mouse/keyboard.
    - Low latency capture compared to ADBDevice, using Scrcpy's video server instead of grabbing raw pngs.

    Remember to call cleanup() when you're done.
    """

    def __init__(
        self,
        capture_size,
        adb_flags,
        fps=settings.get_scrcpydevice_capture_fps(),
        bitrate=settings.get_scrcpydevice_capture_bitrate(),
    ):
        assert "-s" in adb_flags
        for i, v in enumerate(adb_flags):
            if v == "-s":
                self.image_queue, self.event_queue, self.thread = start_listener_thread(
                    adb_flags[i + 1], fps, bitrate
                )
        super(StreamingAndroidDevice, self).__init__(capture_size, adb_flags)

    def cleanup(self):
        self.event_queue.put(SCRCPY_DEVICE_KILL_THREAD)

    def screen_capture_raw(self, crop_settings=None):
        # type: (Optional[tuple[int]]) -> Image
        global image_condition, last_image
        image = None
        with image_condition:
            while True:
                if last_image is not None:
                    image = last_image
                    break
                image_condition.wait()
        return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    def screen_off(self):
        self.event_queue.put(EVENT_SCREEN_OFF)

    def screen_on(self):
        self.event_queue.put(EVENT_SCREEN_ON)


def listener_thread(serial, event_queue, fps, bitrate):
    def on_frame(frame):
        if not event_queue.empty():
            try:
                event = event_queue.get(block=False)
                if event is EVENT_SCREEN_OFF:
                    client.control.set_screen_power_mode(scrcpy.POWER_MODE_OFF)
                if event is EVENT_SCREEN_ON:
                    client.control.set_screen_power_mode(scrcpy.POWER_MODE_NORMAL)
                if event is SCRCPY_DEVICE_KILL_THREAD:
                    client.stop()
            except Empty:
                pass

        if frame is not None:
            global image_condition, last_image
            with image_condition:
                last_image = frame
                image_condition.notify()

    client = scrcpy.Client(device=serial, max_fps=fps, bitrate=bitrate)
    client.add_listener(scrcpy.EVENT_FRAME, on_frame)
    client.start(threaded=False)


def start_listener_thread(serial, fps, bitrate):
    image_queue = LifoQueue()
    event_queue = LifoQueue()
    thread = threading.Thread(
        target=listener_thread,
        daemon=True,
        args=(
            serial,
            event_queue,
            fps,
            bitrate,
        ),
    )
    thread.start()
    return image_queue, event_queue, thread
