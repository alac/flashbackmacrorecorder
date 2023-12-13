import time
import logging


def time_str(seconds):
    """
    Return a string representation of the given number of seconds in the format `hh:mm:ss`.

    Args:
        seconds: The number of seconds to convert.

    Returns:
        A string representation of the given number of seconds in the format `hh:mm:ss`.
    """
    return f"{int(seconds / (60 * 60))}:{int((seconds % (60 * 60)) / 60):02d}:{int(seconds) % 60:02d}"


def sleep_countdown(duration, interval=1.0):
    """
    Print a countdown of the given duration, with a given interval between each print.

    Args:
        duration: The duration of the countdown, in seconds.
        interval: The interval between each print, in seconds.
    """
    end_time = time.time() + duration
    while time.time() < end_time:
        wait_time = end_time - time.time()
        print(f"\rsleeping for {time_str(wait_time)}", end="")
        time.sleep(max(min(interval, end_time - time.time()), 0))


def apply_action_and_wait_to_become_invalid(log_prefix, action_name, success_stat, device, config, state, utils, stats):
    """
    Apply the given action and wait until it becomes invalid.

    Args:
        log_prefix: A prefix to use for logging messages.
        action_name: The name of the action to apply.
        success_stat: The name of the stat to increment if the action succeeds.
    Example case:
    1. A dialog that gets dismissed upon selecting an option.
    2. A menu item that causes the menu itself to change.
    """
    clicked = False
    while True:
        time.sleep(.5)
        image = device.screen_capture()
        action = config.get_action(action_name)
        viability = action.is_valid(image, state, utils)

        logging.getLogger("fbmr_logger").debug(
            f"{log_prefix}: checking ", action.name, " viability ", viability)
        if viability == 0 and not clicked:
            # waiting for the action to become valid
            continue
        elif viability != 0:
            # action is valid, we'll click until it's accepted
            action.apply(image, state, utils)
            clicked = True
        elif viability == 0 and clicked:
            # the action succeeded because it can no longer be performed
            if success_stat and stats:
                stats.increment(success_stat)
            return


def apply_action_and_wait_for_next_action(log_prefix, action_name, next_action_name, success_stat, device, config,
                                          state, utils, stats):
    """
    Apply the given action and wait for the next action to become valid.

    Args:
        log_prefix: A prefix to use for logging messages.
        action_name: The name of the action to apply.
        next_action_name: The name of the next action to wait for.
        success_stat: The name of the stat to increment if the action succeeds.

    Returns:
        None

    Example case:
    1. A button that causes another dialog to appear, _without_ hiding the original button.
    (OpenCV cannot differentiate between colors; a button looks the same even if it's grayed out.)
    """
    clicked = False
    while True:
        time.sleep(.5)
        image = device.screen_capture()
        action = config.get_action(action_name)
        viability = action.is_valid(image, state, utils)

        logging.getLogger("fbmr_logger").debug(
            f"{log_prefix}: checking ", action.name, " viability ", viability)
        if viability == 0 and not clicked:
            # waiting for the action to become valid
            continue
        elif viability != 0:
            # action is valid, we'll click until it's accepted
            action.apply(image, state, utils)
            clicked = True
        elif clicked:
            if config.get_action(next_action_name).is_valid(image, state, utils) != 0:
                # the action succeeded because the next action is available
                if success_stat and stats:
                    stats.increment(success_stat)
                return


def hammer_back_button_until_action_viable(action_name, device, config, state, utils, stats):
    """
    Example cases:
    1. Opening the app causes dialogs to appear (that can be dismissed with BACK).
    2. Returning to the home screen from a nested menu.
    """
    seen = 0
    while True:
        image = device.screen_capture()
        action = config.get_action(action_name)
        viability = action.is_valid(image, state, utils)

        if viability == 0:
            # keep trying to close dialogs
            device.press_back_button()
        else:
            seen += 1
            if seen > 10:  # 5 seconds of just the home screen
                break
        time.sleep(.5)
