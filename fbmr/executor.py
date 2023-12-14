import time
from typing import List, Union, Optional, Tuple
import subprocess
from PIL import Image, ImageDraw
from abc import ABC, abstractmethod
import logging

from fbmr.utils.debug_settings import debug_settings
from fbmr.config import Config, Action
from fbmr.conditions import Condition
from fbmr.helpers import sleep_countdown
from fbmr.utils.settings import settings


class UnreachedExitActionException(ValueError):
    pass


class ActionScore:
    def __init__(self, action_name, score, bounding_box):
        self.action_name = action_name
        self.score = score
        self.bounding_box = bounding_box


class Executor:
    # next_action_names: list[Str]

    def __init__(self):
        self.config = None
        self.next_action_names = []
        self.execution_hook = None  # type: Optional[ExecutionHook]
        self.throw_if_end_action_not_reached = False

    def set_config(self, config: Config):
        self.config = config

    def execute_chain(self, start_action_names: Union[str, list[str]], end_action_names: list[str], state_dict: dict,
                      utils: dict, min_action_delay: float = 0.0, max_minutes: float = 0.0) -> Optional[Action]:
        if type(start_action_names) is str:
            start_action_names = [start_action_names]
        self.next_action_names = start_action_names

        self.execution_hook and self.execution_hook.starting_chain(start_action_names, self.config)

        device = utils["device"]
        start = time.time()
        executed_action = None
        while True:
            debug_settings.check_timeout()

            self.execution_hook and self.execution_hook.searching_for_action(self.next_action_names, self.config)

            minutes = (time.time() - start) / 60
            logging.getLogger("fbmr_logger").info(
                f"action_chain '{start_action_names}' running: {minutes:.2f} minutes; next: {self.next_action_names}")

            action_start = time.time()
            try:
                image = device.screen_capture()
                executed_action = self.execute_best_action(image, state_dict, utils, end_action_names=end_action_names)
                if len(self.next_action_names) == 0:
                    return None
                if executed_action and len(start_action_names) > 1:
                    start_action_names = [executed_action.name]
                if executed_action and end_action_names and executed_action.name in end_action_names:
                    logging.getLogger("fbmr_logger").info(
                        f"action_chain '{start_action_names}' completed -> {executed_action.name}; returning")
                    self.execution_hook and self.execution_hook.chain_completed(start_action_names,
                                                                                executed_action.name, self.config)
                    break
            except subprocess.CalledProcessError:
                logging.getLogger("fbmr_logger").error("adb error")
                time.sleep(10)

            minutes = (time.time() - start) / 60
            if max_minutes != 0 and minutes > max_minutes:
                logging.getLogger("fbmr_logger").warning(
                    f"action_chain '{start_action_names}' max_minutes exceeded; uptime: {minutes} minutes")
                self.execution_hook and self.execution_hook.chain_timed_out(start_action_names, minutes * 60,
                                                                            self.config)
                break

            wait_time = min(float(min_action_delay) - (time.time() - action_start), min_action_delay)
            if wait_time > 0:
                time.sleep(wait_time)
        self.next_action_names = None
        return executed_action

    def score_actions(self, pil_image: Image, state_dict: dict, utils: dict, action_names: List[str]) -> \
            List[ActionScore]:
        action_scores = []  # type: List[ActionScore]
        for action_name in action_names:
            viability, rect = self.config.get_action(action_name).find_valid_rect(pil_image, state_dict, utils)
            action_scores.append(ActionScore(action_name, viability, rect))
        action_scores.sort(key=lambda x: x.score, reverse=True)
        return action_scores

    def execute_best_action(self, pil_image: Image, state_dict: dict, utils: dict,
                            end_action_names: Optional[List[str]] = None) -> Optional[Action]:
        self.next_action_names = [n for n in self.next_action_names if n]
        if len(self.next_action_names) > 0:
            logging.getLogger("fbmr_logger").debug(
                f"execute_best_action: next_action_names {self.next_action_names}")

        action_scores = self.score_actions(
            pil_image,
            state_dict,
            utils,
            self.next_action_names or [a.name for a in self.config.actions])
        action = self.config.get_action(action_scores[0].action_name)

        def confirm_action():
            if self.config.confirmAll:
                confirmation_image = utils["device"].screen_capture()
                confirm_viability = action.is_valid(confirmation_image, state_dict, utils)
                if confirm_viability < 20:
                    logging.getLogger("fbmr_logger").debug(
                        f"execute_best_action: confirm failed {action.name} viability {confirm_viability}")
                    return False
            return True

        annotated_image = annotate_image_with_bounding_boxes(pil_image,
                                                             [(a.score, a.bounding_box) for a in action_scores])
        if action and action_scores[0].score > 20 and confirm_action():
            logging.getLogger("fbmr_logger").info(f"execute_best_action: running {action.name}")
            self.apply_and_wait(action, pil_image, annotated_image, state_dict, utils)
            self.next_action_names = action.next_action_names
            if self.throw_if_end_action_not_reached:
                if not self.next_action_names and end_action_names:
                    raise UnreachedExitActionException(f"execute_best_action: could not reach {end_action_names}")
            return action
        else:
            self.execution_hook and self.execution_hook.action_search_failed(annotated_image, self.config)

        return None

    def apply_and_wait(self, action: Action, pil_image: Image, annotated_image: Image, state_dict: dict, utils: dict):
        if self.execution_hook:
            hook_image = annotated_image or pil_image
            self.execution_hook.performing_action(action, hook_image.copy(), self.config)
        action.apply(pil_image, state_dict, utils)
        self.execution_hook and self.execution_hook.after_action(action, action.cooldown, self.config)
        if action.cooldown:
            logging.getLogger("fbmr_logger").info(f"Waiting for {action.name}'s cooldown: {action.cooldown:.2f}")
            sleep_countdown(action.cooldown, interval=.1)
        if action.advance_if_condition:
            device = utils["device"]
            start_ts = time.time()
            last_retry = start_ts
            retries = 0
            while True:
                debug_settings.check_timeout()
                elapsed = time.time() - start_ts
                retry_duration = settings.get_fbmr_action_retry_duration()

                sc = device.screen_capture()
                self.execution_hook and self.execution_hook.waiting_to_advance(action, sc.copy(), elapsed,
                                                                               retry_duration, retries, self.config)

                # wait for this action to be completed
                if action.advance_if_condition.is_valid(sc, state_dict, utils):
                    logging.getLogger("fbmr_logger").info(f"Action advance_if_condition satisfied")
                    break

                # or for the next action to become available
                def a_next_action_is_valid():
                    for next_action_name in action.next_action_names:
                        if self.config.get_action(next_action_name).is_valid(sc, state_dict, utils):
                            logging.getLogger("fbmr_logger").info(f"Next action became valid")
                            return True
                    return False

                if a_next_action_is_valid():
                    break

                print(f"Waiting for {action.name}'s advance_if_condition: {elapsed:.2f} elapsed", end='\n', flush=True)
                # however, if we get stuck, try to get out of it by repeating the action
                if (time.time() - last_retry) > retry_duration:
                    sc = device.screen_capture()
                    logging.getLogger("fbmr_logger").debug("execute_best_action: checking for retry {action.name}")
                    viability = action.is_valid(sc, state_dict, utils)
                    if viability != 0:
                        retries += 1
                        action.apply(sc, state_dict, utils)
                        logging.getLogger("fbmr_logger").debug(
                            f"execute_best_action: retried {action.name} with viability {viability}")
                        last_retry = time.time()
                time.sleep(.5)
        print("\n", flush=True)

    def check_conditions(self, conditions: List[Condition], message: str, pil_image: Image, state_dict: dict,
                         utils: dict, enable_log=True) -> bool:
        success = True
        annotations = []
        for condition in conditions:
            res, rect = condition.find_valid_rect(pil_image, state_dict, utils)
            success = success and (res >= condition.threshold)
            annotations.append((res, rect))
        annotated_image = annotate_image_with_bounding_boxes(pil_image, annotations)
        self.execution_hook and enable_log and \
            self.execution_hook.check_condition_result(message, success, annotated_image, self.config)
        return success


def annotate_image_with_bounding_boxes(pil_image: Image,
                                       score_and_rect_pairs: List[Tuple[int, Tuple[int, int, int, int]]]) -> Image:
    annotated = pil_image.copy()
    drawer = ImageDraw.Draw(annotated, "RGBA")
    for score, rect in score_and_rect_pairs:
        def get_color():
            red = (255, 0, 0)
            green = (0, 255, 0)

            def interp(a, b):
                return int(a * (100 - score)/100.0 + b * score/100.0)

            return (interp(red[0], green[0]),
                    interp(red[1], green[1]),
                    interp(red[2], green[2]))
        x, y, w, h = rect
        drawer.rectangle((x, y, x + w, y + h), outline=get_color(), width=3)
    return annotated


class ExecutionHook(ABC):
    @abstractmethod
    def starting_chain(self, start_action_names: List[str], config: Config):
        pass

    @abstractmethod
    def chain_completed(self, start_action_names: List[str], last_action_name: str, config: Config):
        pass

    @abstractmethod
    def chain_timed_out(self, start_action_names: List[str], duration: float, config: Config):
        pass

    @abstractmethod
    def searching_for_action(self, next_action_names: List[str], config: Config):
        pass

    @abstractmethod
    def performing_action(self, action: Action, pil_image: Image, config: Config):
        pass

    @abstractmethod
    def after_action(self, action: Action, cooldown: float, config: Config):
        pass

    @abstractmethod
    def waiting_to_advance(self, action: Action, pil_image: Image, waited_time: float, retry_duration: float,
                           retries: int, config: Config):
        pass

    @abstractmethod
    def action_search_failed(self, pil_image: Image, config: Config):
        pass

    @abstractmethod
    def check_condition_result(self, description: str, success: bool, pil_image: Image, config: Config):
        pass
