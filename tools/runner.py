import argparse
import threading
from queue import SimpleQueue, Empty
from typing import Union, Optional, List, Tuple
import os.path
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageTk
import json
import datetime
import tqdm

from fbmr.devices import all_device_constructors
from fbmr.config import Config, Action
from fbmr.conditions import ImageCondition
from fbmr.utils.debug_settings import debug_settings
from fbmr.executor import Executor, ExecutionHook


class RunnerCommand:
    pass


class RunnerStartCommand(RunnerCommand):
    def __init__(self, next_actions: Union[str, List[str]] = None, exit_actions: List[str] = None,
                 max_minutes: float = 0, min_action_delay: float = 0, execution_hook: ExecutionHook = None,
                 state: Optional[dict] = None):
        self.next_actions = next_actions
        self.exit_actions = exit_actions
        self.max_minutes = max_minutes
        self.min_action_delay = min_action_delay
        self.execution_hook = execution_hook
        self.state = state


class RunnerInterruptCommand(RunnerCommand):
    """Dummy Command to allow for interrupts in ExecutionHook. This is a NOOP in the command consumer."""
    pass


class InterruptException(Exception):
    pass


class Runner:
    def __init__(self, config_name, device_name):
        self.config_name = config_name
        self.device_name = device_name

    def run(self, next_actions: Union[str, List[str]] = None, exit_actions: List[str] = None, max_minutes: float = 0.0,
            min_action_delay: float = 0, execution_hook: ExecutionHook = None, state: Optional[dict] = None):
        debug_settings.save_detect_subimage_images = False
        c = Config("configs", self.config_name)
        e = Executor()
        e.set_config(c)
        e.execution_hook = execution_hook

        if not state:
            state = {"viability_adjustment": 0}

        with all_device_constructors()[self.device_name]() as d:
            utils = {"device": d}
            e.execute_chain(next_actions, exit_actions, state, utils, min_action_delay=min_action_delay,
                            max_minutes=max_minutes)

    def start_thread(self, queue: SimpleQueue[RunnerCommand]):
        thread = threading.Thread(target=self.threaded_run, args=(queue,))
        thread.daemon = True
        thread.start()

    def threaded_run(self, queue: SimpleQueue[RunnerCommand]):
        while True:
            command = queue.get(block=True)
            try:
                if isinstance(command, RunnerStartCommand):
                    self.run(command.next_actions, command.exit_actions, command.max_minutes, command.min_action_delay,
                             command.execution_hook, command.state)
                elif isinstance(command, RunnerInterruptCommand):
                    pass
                else:
                    print(f"Runner: Unexpected queue element: {command}")
            except InterruptException:
                pass


class ActionLogEvent:
    def __init__(self, description: str, image_paths: List[str]):
        self.timestamp = datetime.datetime.now()
        self.description = description
        self.image_paths = image_paths
        self.repeats = 0

    @property
    def full_description(self):
        ts = self.timestamp.strftime("%I-%M-%S%p")
        message = f"{ts}: {self.description}"
        if self.repeats > 0:
            message += f" (repeated {self.repeats} times)"
        return message


class ActionSearchEvent:
    def __init__(self, description: str, image: Image):
        self.timestamp = datetime.datetime.now()
        self.description = description
        self.image = image

    @property
    def full_description(self):
        ts = self.timestamp.strftime("%I-%M-%S%p")
        return f"{ts}: {self.description}"


class MacroLogUI:
    def __init__(self):
        self.execution_hook = RunnerUIExecutionHook(SimpleQueue(), SimpleQueue())
        self.action_log_list_images = []
        self.all_action_log_events = []  # type: List[List[ActionLogEvent]]
        self.last_search_event = None  # type: Optional[ActionSearchEvent]

    # noinspection PyAttributeOutsideInit
    def launch_log_ui(self):
        """
        Launch a UI window intended to show the current actions of an __independently__ scripted.

        Because TKInter must run in the main thread, the script that we are observing must be run in a spawned thread.
        So, expected usage is something like:
            import threading

            macro_ui = MacroLogUI()
            def start_macro(execution_hook):
                executor = Executor()
                executor.execution_hook = execution_hook
                executor.start_action_chain(...) // rest of the script
            thread = threading.Thread(target=start_macro, args=(macro_ui.execution_hook,))
            thread.daemon = True
            thread.start()
        """
        # Create the root window
        root = tk.Tk()

        root.geometry("{}x{}+0+0".format(655, root.winfo_screenheight()))
        root.grid_rowconfigure(3, weight=1)

        # Create the widgets
        self.status_label = tk.Label(root, text="Status: Ready")
        next_action_label = tk.Label(root, text="Next Action(s):")
        self.next_action_textfield = tk.Entry(root)
        end_action_label = tk.Label(root, text="End Action:")
        self.end_action_textfield = tk.Entry(root)
        self.action_log_scrolledtext = ScrolledText(root)

        # Set the widget grid positions
        self.status_label.grid(row=0, column=0, columnspan=3, sticky="ew")
        next_action_label.grid(row=1, column=0, sticky="ew")
        self.next_action_textfield.grid(row=1, column=1, sticky="ew")
        end_action_label.grid(row=2, column=0, sticky="ew")
        self.end_action_textfield.grid(row=2, column=1, sticky="ew")
        self.action_log_scrolledtext.grid(row=3, column=0, columnspan=3, sticky="nsew")

        # Run the Tkinter event loop
        self.update_status(root)
        root.mainloop()

    def update_status(self, root: tk.Tk):
        update_command = None
        try:
            while True:
                update_command = self._update_status() or update_command
        except Empty:
            pass

        # update ui
        if update_command:
            trimmed = []
            total_screenshots = 0
            for action_event_list in reversed(self.all_action_log_events):
                if total_screenshots > 10:
                    break
                trimmed.append(action_event_list)
                total_screenshots += sum([len(action_events.image_paths) for action_events in action_event_list])
            trimmed.reverse()
            self.all_action_log_events = trimmed
            self.update_screenshots_list(self.last_search_event, self.all_action_log_events)

        root.after(200, lambda: self.update_status(root))

    def _update_status(self):
        # throws Empty if no elements
        update_command = self.execution_hook.ui_update_queue.get(False)

        if update_command.next_action_names:
            self.next_action_textfield.delete(0, tk.END)
            self.next_action_textfield.insert(0, ",".join(update_command.next_action_names))

        if update_command.status:
            # When a status repeats, only keep the oldest and the most recent
            if self.all_action_log_events and self.all_action_log_events[-1][0].description == update_command.status:
                new_event = ActionLogEvent(update_command.status, [])
                new_event.repeats = 1 + self.all_action_log_events[-1][0].repeats
                if new_event.repeats == 1:
                    self.all_action_log_events.append([new_event])
                else:
                    self.all_action_log_events[-1] = [new_event]
            else:
                self.all_action_log_events.append([ActionLogEvent(update_command.status, [])])
            self.status_label.config(text=update_command.status)

        if update_command.last_search_event:
            self.last_search_event = update_command.last_search_event

        if update_command.action_log_event:
            self.all_action_log_events.append(update_command.action_log_event)

        return update_command

    def update_screenshots_list(self, last_search_event: Optional[ActionSearchEvent],
                                action_log_lists: List[List[ActionLogEvent]]):
        self.action_log_scrolledtext.delete('1.0', tk.END)  # Clear current contents.
        self.action_log_list_images.clear()

        text_field = self.action_log_scrolledtext

        def insert_image_into_textfield(i):
            i.thumbnail((500, 500), Image.ANTIALIAS)
            i = ImageTk.PhotoImage(i)
            text_field.image_create(tk.INSERT, padx=5, pady=5, image=i)
            self.action_log_list_images.append(i)  # Keep a reference.

        if last_search_event:
            escaped_description = last_search_event.full_description.replace('\\', '\\\\')
            text_field.insert(tk.INSERT, f"{escaped_description}\n")
            insert_image_into_textfield(last_search_event.image)
            text_field.insert(tk.INSERT, '\n\n\n-------------------Action Log-----------------------\n')

        for action_logs in reversed(action_log_lists):
            for al in action_logs:
                escaped_description = al.full_description.replace('\\', '\\\\')
                text_field.insert(tk.INSERT, f"{escaped_description}\n")

                for image_path in al.image_paths:
                    insert_image_into_textfield(Image.open(image_path))
                    text_field.insert(tk.INSERT, '\n')
            text_field.insert(tk.INSERT, '\n')


class RunnerUI(MacroLogUI):
    def __init__(self, config_name, device_name):
        super(RunnerUI, self).__init__()
        self.config_name = config_name
        self.device_name = device_name

        self.thread_started = False
        self.runner = None  # type: Optional[Runner]

        self.config = Config("configs", self.config_name)
        self.popup_image_cache = []

    # noinspection PyAttributeOutsideInit
    def launch_runner_ui(self, start_actions: List[str], end_actions: List[str]):
        """
        Launch a UI window intended to control (start/stop) the macro playback.
        """
        # Create the root window
        root = tk.Tk()

        root.geometry("{}x{}+0+0".format(655, root.winfo_screenheight()))
        root.grid_rowconfigure(4, weight=1)

        # Create the widgets
        start_button = tk.Button(root, text="Start", command=lambda: self.forward_start_command())
        interrupt_button = tk.Button(root, text="Interrupt", command=lambda: self.forward_interrupt_command())
        self.status_label = tk.Label(root, text=f"Status: Loaded Config with {len(self.config.actions)} actions")
        next_action_label = tk.Label(root, text="Next Action(s):")
        self.next_action_textfield = tk.Entry(root)
        self.next_action_textfield.insert(0, ",".join(start_actions))
        choose_next_action_button = tk.Button(root, text="Choose Next Action",
                                              command=lambda: self.choose_next_action())
        end_action_label = tk.Label(root, text="End Action:")
        self.end_action_textfield = tk.Entry(root)
        self.end_action_textfield.insert(0, ",".join(end_actions))
        choose_end_action_button = tk.Button(root, text="Choose End Action", command=lambda: self.choose_end_action())
        self.action_log_scrolledtext = ScrolledText(root)

        # Set the widget grid positions
        start_button.grid(row=0, column=0, sticky="ew")
        interrupt_button.grid(row=0, column=1, sticky="ew")
        self.status_label.grid(row=1, column=0, columnspan=3, sticky="ew")
        next_action_label.grid(row=2, column=0, sticky="ew")
        self.next_action_textfield.grid(row=2, column=1, sticky="ew")
        choose_next_action_button.grid(row=2, column=2, sticky="ew")
        end_action_label.grid(row=3, column=0, sticky="ew")
        self.end_action_textfield.grid(row=3, column=1, sticky="ew")
        choose_end_action_button.grid(row=3, column=2, sticky="ew")
        self.action_log_scrolledtext.grid(row=4, column=0, columnspan=3, sticky="nsew")

        # Run the Tkinter event loop
        self.update_status(root)
        root.mainloop()

    def start_thread(self):
        if not self.thread_started:
            self.thread_started = True
            self.runner = Runner(self.config_name, self.device_name)
            self.runner.start_thread(self.execution_hook.runner_queue)

    def forward_start_command(self):
        self.start_thread()
        start_actions = [s for s in self.next_action_textfield.get().split(",") if s]
        end_actions = [s for s in self.end_action_textfield.get().split(",") if s]
        command = RunnerStartCommand(next_actions=start_actions, exit_actions=end_actions, max_minutes=0,
                                     min_action_delay=.5, execution_hook=self.execution_hook)
        self.execution_hook.runner_queue.put(command)

    def forward_interrupt_command(self):
        self.start_thread()
        self.execution_hook.runner_queue.put(RunnerInterruptCommand())

    def choose_next_action(self):
        win = tk.Toplevel()
        win.wm_title("Choose 'Next Action'")
        win.geometry("{}x{}+0+0".format(550, win.winfo_screenheight()))

        def callback(action_name: str):
            self.next_action_textfield.delete(0, tk.END)
            self.next_action_textfield.insert(0, action_name)
            win.destroy()
            self.popup_image_cache = []

        populate_menu(win, self.popup_image_cache, get_images_and_action_names_from_config(self.config), callback)

    def choose_end_action(self):
        win = tk.Toplevel()
        win.wm_title("Choose 'End Action'")
        win.geometry("{}x{}+0+0".format(550, win.winfo_screenheight()))

        def callback(action_name: str):
            self.end_action_textfield.delete(0, tk.END)
            self.end_action_textfield.insert(0, action_name)
            win.destroy()
            self.popup_image_cache = []

        populate_menu(win, self.popup_image_cache, get_images_and_action_names_from_config(self.config), callback)


def get_images_and_action_names_from_config(config: Config):
    result = []

    for action in config.actions:
        name = action.name
        image_path = None

        for condition in action.conditions:
            if isinstance(condition, ImageCondition):
                image_fp = condition.adjust_file_path(condition.image_path)
                # use the "_outline" image if it exists since it shows the entire screenshot where the condition
                # is expected to be valid
                outline_fp = image_fp.replace("_tap", "_outline")
                if os.path.exists(outline_fp):
                    image_path = outline_fp
                elif os.path.exists(image_fp):
                    if not image_path:
                        image_path = image_fp

        result.append((image_path, name))
    return result


def populate_menu(window: tk.Toplevel, img_cache: List, paths_and_labels: List[Tuple[str, str]], callback_fn):
    # Create a frame to hold the canvas and scrollbar
    frame = tk.Frame(window)
    frame.pack(fill='both', expand=True)

    # Create a canvas widget
    canvas = tk.Canvas(frame)
    canvas.pack(side='left', fill='both', expand=True)

    # Create a scrollbar widget
    scrollbar = tk.Scrollbar(frame, orient='vertical', command=canvas.yview)
    scrollbar.pack(side='right', fill='y')

    # Connect the canvas and scrollbar
    canvas.configure(yscrollcommand=scrollbar.set)

    # Create a frame to hold the image and button pairs
    inner_frame = tk.Frame(canvas)

    # Create a button for each image
    for path, label_text in (pbar := tqdm.tqdm(paths_and_labels)):
        pbar.set_description(f"Loading '{label_text}'")
        tk.Label(inner_frame, text=label_text).pack()

        if not path:
            tk.Label(inner_frame, text="[IMAGE MISSING]").pack()
            continue

        # Open the image and convert it to a PhotoImage object
        image = Image.open(path)
        image.thumbnail((500, 500))
        img_cache.append(ImageTk.PhotoImage(image))

        # Create a button for the image
        button = tk.Button(inner_frame, image=img_cache[-1], command=lambda x=label_text: callback_fn(x))
        button.pack()

    # Create a window to hold the inner frame in the canvas
    canvas.create_window((0, 0), window=inner_frame, anchor='nw')

    # Set the size of the canvas window
    inner_frame.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox('all'))


class UIUpdatesCommand:
    def __init__(self, status: str, next_action_names: Optional[List[str]] = None,
                 last_search_event: Optional[ActionSearchEvent] = None,
                 action_log_event: Optional[List[ActionLogEvent]] = None):
        self.status = status
        self.next_action_names = next_action_names
        self.last_search_event = last_search_event
        self.action_log_event = action_log_event


class RunnerUIExecutionHook(ExecutionHook):
    """Expected to be called in the runner thread"""
    def __init__(self, runner_queue: SimpleQueue[RunnerCommand], ui_update_queue: SimpleQueue[UIUpdatesCommand]):
        self.runner_queue = runner_queue
        self.ui_update_queue = ui_update_queue
        self.search_state = None

    def check_for_queued_command(self):
        if not self.runner_queue.empty():
            raise InterruptException("Queued RunnerCommand detected")

    def starting_chain(self, start_action_names: List[str], config: Config):
        self.check_for_queued_command()
        self.search_state = None
        command = UIUpdatesCommand(f"Starting chain: {start_action_names}",
                                   action_log_event=self.screenshot_data_for_next_action_names(start_action_names,
                                                                                               config))
        self.ui_update_queue.put(command)

    def chain_completed(self, start_action_names: List[str], last_action_name: str, config: Config):
        self.check_for_queued_command()
        command = UIUpdatesCommand(f"Completed chain from {start_action_names} to {last_action_name}")
        self.ui_update_queue.put(command)

    def chain_timed_out(self, start_action_names: List[str], duration: float, config: Config):
        self.check_for_queued_command()
        command = UIUpdatesCommand(f"Executing chain {start_action_names} timed out after {duration}")
        self.ui_update_queue.put(command)

    def searching_for_action(self, next_action_names: List[str], config: Config):
        self.check_for_queued_command()
        if self.search_state and str(self.search_state) == str(next_action_names):
            return
        self.search_state = next_action_names
        command = UIUpdatesCommand(f"Searching for action from {next_action_names}",
                                   next_action_names=next_action_names,
                                   action_log_event=self.screenshot_data_for_next_action_names(next_action_names,
                                                                                               config))
        self.ui_update_queue.put(command)

    def action_search_failed(self, pil_image: Image, config: Config):
        search_event = ActionSearchEvent(f"Search Failed", pil_image)
        command = UIUpdatesCommand(f"Search Failed", last_search_event=search_event)
        self.ui_update_queue.put(command)

    def performing_action(self, action: Action, pil_image: Image, config: Config):
        self.check_for_queued_command()
        self.search_state = None
        search_event = ActionSearchEvent(f"Performing action {action.name}", pil_image)
        command = UIUpdatesCommand(f"Performing action {action.name}", last_search_event=search_event)
        self.ui_update_queue.put(command)

    def after_action(self, action: Action, cooldown: float, config: Config):
        self.check_for_queued_command()
        command = UIUpdatesCommand(f"Performing action {action.name} cooldown for {cooldown:.2f}")
        self.ui_update_queue.put(command)

    def waiting_to_advance(self, action: Action, pil_image: Image, waited_time: float, retry_duration: float,
                           retries: int, config: Config):
        self.check_for_queued_command()
        search_event = ActionSearchEvent(f"Waiting to advance", pil_image)
        command = UIUpdatesCommand(
            f"Advancing from {action.name}; waited {waited_time:.2f}; retry after {retry_duration:.2f};"
            + f" retries {retries}", last_search_event=search_event)
        self.ui_update_queue.put(command)

    def check_condition_result(self, description: str, success: bool, pil_image: Image, config: Config):
        message = {
            True: "Condition Matched",
            False: "Condition Failed",
        }[success]
        if description:
            message = f"{message}: {description}"
        search_event = ActionSearchEvent(message, pil_image)
        command = UIUpdatesCommand(message, last_search_event=search_event)
        self.ui_update_queue.put(command)

    @staticmethod
    def screenshot_data_for_next_action_names(next_action_names: List[str], config: Config) \
            -> List[ActionLogEvent]:
        result = list()  # type: List[ActionLogEvent]
        for action_name in next_action_names:
            action = config.get_action(action_name)
            if len(action.conditions) == 0:
                continue
            result.append(ActionLogEvent(f"Action: {action_name}, with {len(action.conditions)} condition(s)",
                                         []))
            for condition in action.conditions:
                image_path = None
                if isinstance(condition, ImageCondition):
                    image_fp = condition.adjust_file_path(condition.image_path)
                    # use the "_outline" image if it exists since it shows the entire screenshot where the condition
                    # is expected to be valid
                    outline_fp = image_fp.replace("_tap", "_outline")
                    if os.path.exists(outline_fp):
                        image_path = outline_fp
                    elif os.path.exists(image_fp):
                        image_path = image_fp
                result.append(ActionLogEvent("Condition: " + json.dumps(condition.make_json()),
                                             [image_path]))
            return result


def main():
    # Create the ArgumentParser object
    parser = argparse.ArgumentParser()

    # Add the required positional arguments
    parser.add_argument("config", help="the config file to use", type=str)
    parser.add_argument("device", help="the shorthand name for the device to use; specified in devices.py", type=str)

    # Add the optional arguments
    parser.add_argument("--next_action", help="the first action to perform", type=str, default=None)
    parser.add_argument("--end_action", help="terminate execution after this action", type=str, default=None)
    parser.add_argument('--ui', action='store_true', default=False, help='show a UI to control and monitor the run')
    parser.add_argument('--debug', action='store_true', default=False, help='includes the "image match" logging in the'
                        ' console and saves images to the /debug folder.')
    args = parser.parse_args()

    if args.debug:
        debug_settings.save_detect_subimage_images = True
        debug_settings.log_detect_subimage = True
    next_actions = []
    if args.next_action:
        next_actions.append(args.next_action)
    end_actions = []
    if args.end_action:
        end_actions.append(args.end_action)
    if args.ui:
        runner_ui = RunnerUI(args.config, args.device)
        runner_ui.launch_runner_ui(next_actions, end_actions)
    else:
        runner = Runner(args.config, args.device)
        runner.run(next_actions, end_actions)


if __name__ == "__main__":
    main()
