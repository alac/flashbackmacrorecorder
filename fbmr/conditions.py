import logging
import os
from PIL import Image
from typing import Optional, Tuple, Callable, TypeAlias

from fbmr.utils.detect_image import find_location_path_pil, pad_region


class Condition(object):
    def __init__(self):
        self.folder_path = None
        self.threshold = 0

    def find_valid_rect(self, pil_image: Image, state_dict: dict, utils: dict) -> (int, Tuple[int, int, int, int]):
        # return a value from 0 to 100, signifying the certainty of the match
        raise NotImplementedError("Condition.make_json() not implemented")

    def is_valid(self, pil_image: Image, state_dict: dict, utils: dict) -> int:
        # return a value from 0 to 100, signifying the certainty of the match
        res, _rect = self.find_valid_rect(pil_image, state_dict, utils)
        return res

    def set_folder_path(self, folder_path: str):
        self.folder_path = folder_path

    def adjust_file_path(self, path: str) -> str:
        if path.startswith("configs"):
            # already relative to script root (eg. configs/[category]/...)
            return path
        else:
            if self.folder_path:
                # relative to the config folder, append the path to the config folder
                return os.path.join(self.folder_path, path)
            else:
                return path

    def make_json(self) -> dict:
        raise NotImplementedError("Condition.make_json() not implemented")


def load_condition(c_data: dict, folder_path: str) -> Condition:
    assert "type" in c_data
    condition_type = c_data["type"]

    if condition_type == "SubimageCondition":
        condition = SubimageCondition.load(c_data)
    elif condition_type == "NotSubimageCondition":
        condition = NotSubimageCondition.load(c_data)
    else:
        raise ValueError("Couldn't load condition type {0}".format(condition_type))
    condition.set_folder_path(folder_path)
    return condition


ImageValidityTest: TypeAlias = Callable[[float, float], bool]


class ImageCondition(Condition):
    def __init__(self, image_path: str, intended_region: Optional[list[float, float, float, float]], threshold: float,
                 weight: Optional[float] = 1.0, save_region_as: Optional[str] = False,
                 should_pad_region: Optional[bool] = True):
        super(ImageCondition, self).__init__()
        self.image_path = image_path  # strong
        # pil crop region (left, upper, right, lower)
        self.intended_region = intended_region
        # integer between 0 and 100. valid if match strength exceeds it
        self.threshold = threshold
        # multiplier applied to match strength before returning; use to inflate fuzzier matches
        self.weight = weight
        # string for saving the match region in the state_dict
        self.save_region_as = save_region_as
        self.should_pad_region = should_pad_region

    def find_valid_rect(self, pil_image: Image, state_dict: dict, utils: dict) -> (float, Tuple[int, int, int, int]):
        raise NotImplementedError("ImageCondition.find_valid_rect() not implemented")

    def find_image(self, pil_image: Image, validity_test: ImageValidityTest, state_dict: dict, _utils: dict) -> \
            (float, Tuple[int, int, int, int]):
        cropped_image = pil_image
        cropped_region = None
        if self.intended_region:
            cropped_region = self.intended_region
            if self.should_pad_region:
                cropped_region = pad_region(self.intended_region, pil_image.size)
            cropped_image = pil_image.crop(cropped_region)

        a_image_path = self.adjust_file_path(self.image_path)
        strength, box = find_location_path_pil(a_image_path, cropped_image)
        x, y, t_width, t_height = box

        updated_box = box
        if self.intended_region and cropped_region:
            c_l, c_t, c_r, c_b = cropped_region
            updated_box = (x + c_l, y + c_t, t_width, t_height)

        scaled_strength = strength * self.weight * 100 + state_dict.get("viability_adjustment", 0)
        logging.getLogger("fbmr_logger").debug(
            f'{self.__class__.__name__} match {int(scaled_strength)}/{self.threshold} for {self.image_path}')
        if validity_test(scaled_strength, self.threshold):
            if self.save_region_as:
                state_dict[self.save_region_as] = updated_box
            return scaled_strength, updated_box
        return 0, updated_box

    def make_json(self) -> dict:
        raise NotImplementedError("Condition.make_json() not implemented")


class SubimageCondition(ImageCondition):
    def __init__(self, image_path: str, intended_region: Optional[list[float, float, float, float]], threshold: float,
                 weight: Optional[float] = 1.0, save_region_as: Optional[str] = False,
                 should_pad_region: Optional[bool] = True):
        super(SubimageCondition, self).__init__(image_path, intended_region, threshold, weight, save_region_as,
                                                should_pad_region)

    def find_valid_rect(self, pil_image: Image, state_dict: dict, utils: dict) -> (float, Tuple[int, int, int, int]):
        def validity_test(strength: float, threshold: float):
            return strength > threshold
        return self.find_image(pil_image, validity_test, state_dict, utils)

    @staticmethod
    def load(json_data: dict):
        return SubimageCondition(
            json_data.get("image_path"),
            json_data.get("intended_region", None),
            json_data.get("threshold", 80),
            json_data.get("weight", 1.0),
            json_data.get("save_region_as", None),
        )

    def make_json(self) -> dict:
        d = {"type": "SubimageCondition", "image_path": self.image_path, "intended_region": self.intended_region,
             "threshold": self.threshold, "weight": self.weight, "save_region_as": self.save_region_as}
        return d


class NotSubimageCondition(ImageCondition):
    def __init__(self, image_path: str, intended_region: Optional[list[float, float, float, float]], threshold: float,
                 weight: Optional[float] = 1.0, save_region_as: Optional[str] = False,
                 should_pad_region: Optional[bool] = True):
        super(NotSubimageCondition, self).__init__(image_path, intended_region, threshold, weight, save_region_as,
                                                   should_pad_region)

    def find_valid_rect(self, pil_image: Image, state_dict: dict, utils: dict) -> (float, Tuple[int, int, int, int]):
        def validity_test(strength: float, threshold: float):
            return strength < threshold

        res, rect = self.find_image(pil_image, validity_test, state_dict, utils)
        if res > 0:
            return 100, rect
        return 0, rect

    @staticmethod
    def load(json_data: dict):
        return NotSubimageCondition(
            json_data.get("image_path"),
            json_data.get("intended_region", None),
            json_data.get("threshold", 80),
            json_data.get("weight", 1.0),
            json_data.get("save_region_as", None),
        )

    def make_json(self) -> dict:
        d = {"type": "NotSubimageCondition", "image_path": self.image_path, "intended_region": self.intended_region,
             "threshold": self.threshold, "weight": self.weight, "save_region_as": self.save_region_as}
        return d
