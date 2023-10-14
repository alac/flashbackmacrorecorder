import os
from PIL import Image
from random import randint
from typing import Optional, Callable, TypeAlias

from fbmr.utils.detect_image import find_location_path_pil, find_location_multi_path_pil, pad_region


def variation() -> int:
    return randint(-1, 1)


class Effect(object):
    def __init__(self):
        self.folder_path = None

    def apply(self, pil_image, state_dict, utils):
        # type: (Image, dict, dict) -> None
        # either modify state_dict in place
        # or use a property of utils to perform some action
        pass

    def set_folder_path(self, folder_path):
        # type: (str) -> None
        self.folder_path = folder_path

    def adjust_file_path(self, path):
        # type: (str) -> str
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


def load_effect(e_data: dict, folder_path: str) -> Effect:
    assert "type" in e_data
    effect_type = e_data["type"]

    if effect_type == "ClickSubimageEffect":
        effect = ClickSubimageEffect.load(e_data)
    elif effect_type == "ClickSubimageNearestEffect":
        effect = ClickSubimageNearestEffect.load(e_data)
    elif effect_type == "ClickRelativeRegionEffect":
        effect = ClickRelativeRegionEffect.load(e_data)
    elif effect_type == "DragSubimageEffect":
        effect = DragSubimageEffect.load(e_data)
    elif effect_type == "ScrollRegionEffect":
        effect = ScrollRegionEffect.load(e_data)
    elif effect_type == "ScrollRelativeRegionEffect":
        effect = ScrollRelativeRegionEffect.load(e_data)
    else:
        raise ValueError("Couldn't load effect type {0}".format(effect_type))
    effect.set_folder_path(folder_path)
    return effect


class ClickRegionEffect(Effect):
    def __init__(self, intended_region:  Optional[list[int, int, int, int]]):
        super(ClickRegionEffect, self).__init__()
        self.intended_region = intended_region

    @staticmethod
    def load(json_data: dict):
        return ClickRegionEffect(
            json_data.get("intended_region", None),
        )

    def make_json(self) -> dict:
        d = {
            "type": "ClickRegionEffect",
            "intended_region": self.intended_region,
        }
        return d

    def apply(self, pil_image: Image, state_dict: dict, utils: dict):
        l, t, r, b = self.intended_region
        x, y = (l + r) / 2, (t + b) / 2
        print("    ClickRegionEffect clicking at ", x, ", ", y)
        utils["device"].click(x + variation(), y + variation())


class ClickSubimageEffect(Effect):
    def __init__(self, image_path: str, intended_region:  Optional[list[int, int, int, int]],
                 tap_coords_in_image: Optional[list[int, int]]):
        super(ClickSubimageEffect, self).__init__()
        self.image_path = image_path
        self.intended_region = intended_region
        self.tap_coords_in_image = tap_coords_in_image

    @staticmethod
    def load(json_data: dict):
        return ClickSubimageEffect(
            json_data.get("image_path"),
            json_data.get("intended_region", None),
            json_data.get("tap_coords_in_image", None)
        )

    def make_json(self) -> dict:
        d = {
            "type": "ClickSubimageEffect",
            "image_path": self.image_path,
            "intended_region": self.intended_region,
            "tap_coords_in_image": self.tap_coords_in_image
        }
        return d

    def apply(self, pil_image: Image, state_dict: dict, utils: dict):
        cropped_image = pil_image
        padded_region = None
        if self.intended_region:
            padded_region = pad_region(self.intended_region, pil_image.size)
            cropped_image = pil_image.crop(padded_region)

        a_image_path = self.adjust_file_path(self.image_path)
        _strength, box = find_location_path_pil(
            a_image_path, cropped_image)
        x, y, t_width, t_height = box

        if self.intended_region and padded_region:
            c_l, c_t, c_r, c_b = padded_region
            x = x + c_l
            y = y + c_t

        if self.tap_coords_in_image:
            tx, ty = self.tap_coords_in_image
            x, y = (x + tx, y + ty)
        else:
            x, y = (x + t_width / 2, y + t_height / 2)
        print("    ClickSubimageEffect clicking at ", x, ", ", y)
        utils["device"].click(x + variation(), y + variation())


RegionRegionTest: TypeAlias = Optional[Callable[[list[int, int, int, int], list[int, int, int, int]], bool]]


class ClickSubimageNearestEffect(Effect):
    """
    ClickSubimageNearestEffect handles the case where there are similar looking buttons
    that are differentiated by images near them. Think a table where each row has unique "thumbnail icons"
    and identical "select" buttons.
    We call the "icon" a "match" (because that's what we're seeking out) and the "select button" a
    "click".
    apply() method is configurable via 'validate' property which will filter the "click" candidates.
    """

    def __init__(self, match_path: str, click_path: str,
                 validator: RegionRegionTest = None):
        super(ClickSubimageNearestEffect, self).__init__()
        self.match_path = match_path
        self.click_path = click_path
        self._validator = validator

    @property
    def validator(self) -> RegionRegionTest:
        """The validator takes in two bounding boxes (the found object and the candidate click object)
        and returns a bool that determines whether to accept that candidate click object."""
        return self._validator
    
    @validator.setter
    def validator(self, value: RegionRegionTest):
        self._validator = value

    @staticmethod
    def load(json_data: dict):
        return ClickSubimageNearestEffect(
            json_data.get("match_path"),
            json_data.get("click_path"),
        )

    def make_json(self) -> dict:
        d = {
            "type": "ClickSubimageNearestEffect",
            "match_path": self.match_path,
            "click_path": self.click_path
        }
        return d

    def apply(self, pil_image: Image, state_dict: dict, utils: dict):
        a_match_path = self.adjust_file_path(self.match_path)
        a_click_path = self.adjust_file_path(self.click_path)

        # find the original location
        strength, original_box = find_location_path_pil(a_match_path, pil_image)
        assert strength > .1
        x, y, t_width, t_height = original_box
        # remember the center
        original_x = x + t_width / 2
        original_y = y + t_height / 2

        clickable_locations = find_location_multi_path_pil(a_click_path, pil_image, .5)

        best_location = None
        best_distance = None
        for clickable_location in clickable_locations:
            strength, location_box = clickable_location

            lx, ly, lw, lh = location_box
            lxc = lx + lw / 2
            lyc = ly + lh / 2
            distance = (original_x - lxc) * (original_x - lxc) + (original_y - lyc) * (original_y - lyc)

            if self._validator:
                if not self._validator(original_box, location_box):
                    continue

            if best_distance is None or distance < best_distance:
                best_location = location_box
                best_distance = distance
                continue

        if best_location is None:
            print("    ClickSubimageEffectNearest NO MATCHES")
            return

        x, y, t_width, t_height = best_location
        x, y = (x + t_width / 2, y + t_height / 2)
        print("    ClickSubimageEffectNearest clicking at ", x, ", ", y)
        utils["device"].click(x + variation(), y + variation())


def validator_common_vertical_range(region_a: list[int, int, int, int], region_b: list[int, int, int, int]) -> bool:
    """
    For use with 'ClickSubimageNearestEffect'
    Checks for:
    AAAAAXXXXX
    AAAAAXXXBB
    XXXXXXXXBB
    """
    x1, y1, w1, h1 = region_a
    x2, y2, w2, h2 = region_b

    def box_contains_point(box1, py):
        _x1, _y1, _w1, _h1 = box1
        return (_y1 < py) and ((_y1 + _h1) > py)

    return (box_contains_point(region_a, y2)
            or box_contains_point(region_a, y2 + h2)
            or box_contains_point(region_b, y1)
            or box_contains_point(region_b, y1 + h1))


def validator_common_horizontal_range(region_a: list[int, int, int, int], region_b: list[int, int, int, int]) -> bool:
    """
    For use with 'ClickSubimageNearestEffect'
    Checks for:
    AAAAAXXXXX
    XXXXXXXXXX
    XXXBBBBBBX
    """
    x1, y1, w1, h1 = region_a
    x2, y2, w2, h2 = region_b

    def box_contains_point(box1, ph):
        _x1, _y1, _w1, _h1 = box1
        return (_x1 < ph) and ((_x1 + _w1) > ph)

    return (box_contains_point(region_a, x2)
            or box_contains_point(region_a, x2 + w2)
            or box_contains_point(region_b, x1)
            or box_contains_point(region_b, x1 + w1))


class ClickRelativeRegionEffect(Effect):
    """
    Uses two reference images A and B. Clicks the location of B in A.
    For situations where the button image varies, but the button does not.
    """

    def __init__(self, click_image_path: str, scene_image_path: str):
        super(ClickRelativeRegionEffect, self).__init__()
        self.click_image_path = click_image_path
        self.scene_image_path = scene_image_path

    @staticmethod
    def load(json_data: dict):
        return ClickRelativeRegionEffect(
            json_data.get("click_image_path"),
            json_data.get("scene_image_path"),
        )

    def make_json(self) -> dict:
        d = {"type": "ClickRelativeRegionEffect", "click_image_path": self.click_image_path,
             "scene_image_path": self.scene_image_path}
        return d

    def apply(self, pil_image: Image, state_dict: dict, utils: dict):
        a_click_image_path = self.adjust_file_path(self.click_image_path)
        a_scene_image_path = self.adjust_file_path(self.scene_image_path)

        scene_image = Image.open(a_scene_image_path)

        strength, box = find_location_path_pil(
            a_click_image_path, scene_image)
        assert strength > .1
        x, y, t_width, t_height = box
        x, y = (x + t_width / 2, y + t_height / 2)

        # move from the coordinate system of the example to the device
        capture_size = pil_image.size
        example_size = scene_image.size
        x = int(x * capture_size[0] / example_size[0])
        y = int(y * capture_size[1] / example_size[1])

        print("    ClickSubimageEffect clicking at ", x, ", ", y)
        utils["device"].click(x + variation(), y + variation())


class DragSubimageEffect(Effect):
    """
    Drags from the location of 'image_path' in the screenshot, by a certain movement amount for some duration.
    """

    def __init__(self, image_path: str, intended_region: Optional[list[int, int, int, int]],
                 tap_coords_in_image: list[int, int],
                 movement_amount: list[int, int], duration: float):
        super(DragSubimageEffect, self).__init__()
        self.image_path = image_path
        self.intended_region = intended_region
        self.tap_coords_in_image = tap_coords_in_image
        self.movement_amount = movement_amount
        self.duration = duration

    @staticmethod
    def load(json_data: dict):
        return DragSubimageEffect(
            json_data.get("image_path"),
            json_data.get("intended_region"),
            json_data.get("tap_coords_in_image"),
            json_data.get("movement_amount"),
            json_data.get("duration"),
        )

    def make_json(self) -> dict:
        d = {"type": "DragSubimageEffect", "image_path": self.image_path, "intended_region": self.intended_region,
             "tap_coords_in_image": self.tap_coords_in_image, "movement_amount": self.movement_amount,
             "duration": self.duration}
        return d

    def apply(self, pil_image: Image, state_dict: dict, utils: dict):
        cropped_image = pil_image
        padded_region = None
        if self.intended_region:
            padded_region = pad_region(self.intended_region, pil_image.size)
            cropped_image = pil_image.crop(padded_region)

        a_image_path = self.adjust_file_path(self.image_path)
        strength, box = find_location_path_pil(
            a_image_path, cropped_image)
        assert strength > .1
        x, y, t_width, t_height = box

        if self.intended_region and padded_region:
            c_l, c_t, c_r, c_b = padded_region
            x = x + c_l
            y = y + c_t

        if self.tap_coords_in_image:
            tx, ty = self.tap_coords_in_image
            x, y = (x + tx, y + ty)
        else:
            x, y = (x + t_width / 2, y + t_height / 2)

        dx, dy = self.movement_amount
        x2, y2 = x + dx, y + dy

        print(f"    DragSubimageEffect scrolling from {x}, {y} to {x2}, {y2}")
        utils["device"].swipe(x + variation(), y + variation(), x2 + variation(), y2 + variation(), self.duration)


class ScrollRegionEffect(Effect):
    """
    Scrolls from named locations "start" to "end" wherever "image_path" is found in the current screenshot.
    """

    def __init__(self, image_path: str, start: str, end: str):
        super(ScrollRegionEffect, self).__init__()
        self.image_path = image_path
        self.start = start
        self.end = end

    @staticmethod
    def load(json_data: dict):
        return ScrollRegionEffect(
            json_data.get("image_path"),
            json_data.get("start"),
            json_data.get("end"),
        )

    def make_json(self) -> dict:
        d = {"type": "ScrollRegionEffect", "image_path": self.image_path, "start": self.start, "end": self.end}
        return d

    def apply(self, pil_image: Image, state_dict: dict, utils: dict):
        a_image_path = self.adjust_file_path(self.image_path)

        # find the original location
        strength, box = find_location_path_pil(
            a_image_path, pil_image)
        assert strength > .1

        start_x, start_y = get_location_from_name(self.start, box)
        end_x, end_y = get_location_from_name(self.end, box)

        print(f"    ScrollRegionEffect scrolling from {start_x}, {start_y} to {end_x}, {end_y}")

        utils["device"].swipe(start_x + variation(), start_y + variation(), end_x + variation(), end_y + variation(), 0)


class ScrollRelativeRegionEffect(Effect):
    """
    Uses two reference images A and B. B defines a region in A.
    Scrolls from a 'start' to an 'end' of the region B.
    For situations where the scroll region varies visually (e.g. a table), but the behavior does not.
    """

    def __init__(self, scroll_image_path: str, scene_image_path: str, start: str, end: str):
        super(ScrollRelativeRegionEffect, self).__init__()
        self.scroll_image_path = scroll_image_path
        self.scene_image_path = scene_image_path
        self.start = start
        self.end = end

    @staticmethod
    def load(json_data: dict):
        return ScrollRelativeRegionEffect(
            json_data.get("scroll_image_path"),
            json_data.get("scene_image_path"),
            json_data.get("start"),
            json_data.get("end"),
        )

    def make_json(self) -> dict:
        d = {"type": "ScrollRelativeRegionEffect", "scroll_image_path": self.scroll_image_path,
             "scene_image_path": self.scene_image_path, "start": self.start, "end": self.end}
        return d

    def apply(self, pil_image: Image, state_dict: dict, utils: dict):
        a_scroll_image_path = self.adjust_file_path(self.scroll_image_path)
        a_scene_image_path = self.adjust_file_path(self.scene_image_path)

        scene_image = Image.open(a_scene_image_path)

        strength, box = find_location_path_pil(
            a_scroll_image_path, scene_image)
        assert strength > .1

        start_x, start_y = get_location_from_name(self.start, box)
        end_x, end_y = get_location_from_name(self.end, box)

        # move from the coordinate system of the example to the device
        capture_size = pil_image.size
        example_size = scene_image.size

        start_x = int(start_x * capture_size[0] / example_size[0])
        start_y = int(start_y * capture_size[1] / example_size[1])
        end_x = int(end_x * capture_size[0] / example_size[0])
        end_y = int(end_y * capture_size[1] / example_size[1])

        print(f"    ScrollRelativeRegionEffect scrolling from {start_x}, {start_y} to {end_x}, {end_y}")

        utils["device"].swipe(start_x + variation(), start_y + variation(), end_x + variation(), end_y + variation(), 0)


def get_location_from_name(name: str, box: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, t_width, t_height = box

    if name == "top":
        return int(x + t_width / 2), y
    if name == "bottom":
        return int(x + t_width / 2), y + t_height
    if name == "left":
        return x, int(y + t_height / 2)
    if name == "right":
        return int(x + t_width / 2), int(y + t_height / 2)
    if name == "tl":
        return x, y
    if name == "tr":
        return x + t_width, y
    if name == "bl":
        return x, y + t_height
    if name == "br":
        return x + t_width, y + t_height

    raise ValueError(f"Invalid name {name}")
