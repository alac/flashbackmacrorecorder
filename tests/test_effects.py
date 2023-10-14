from fbmr.effects import ClickSubimageEffect, ClickSubimageNearestEffect, validator_common_vertical_range, \
    validator_common_horizontal_range, ClickRelativeRegionEffect, DragSubimageEffect, ScrollRegionEffect, \
    ScrollRelativeRegionEffect

from PIL import Image

from fbmr import effects
effects.variation = lambda: 0

TESTDATA_COND = "tests/test_data_effect/"


class MockDevice(object):
    def click(self, x, y):
        self.last_method = "click"
        self.last_args = [x, y]

    def swipe(self, x, y, x2, y2, duration):
        self.last_method = "swipe"
        self.last_args = [x, y, x2, y2, duration]

    def print(self):
        print(f"device called {self.last_method} with {self.last_args}")


def test_ClickSubimageEffect():
    effect = ClickSubimageEffect(
        TESTDATA_COND + "button.png",
        None,
        None
    )

    # test jsonification
    json_data = effect.make_json()
    for key in ["type", "image_path", "intended_region", "tap_coords_in_image"]:
        assert key in json_data

    effect2 = ClickSubimageEffect.load(json_data)
    json_data2 = effect2.make_json()
    for key in json_data:
        assert json_data[key] == json_data2[key]

    device = MockDevice()
    # click
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    x, y = device.last_args
    assert abs(823.0 - x) < 10.0 and abs(1053.0 - y) < 10.0

    # click in region
    effect.intended_region = (603, 914, 603 + 503, 914 + 346)
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    x, y = device.last_args
    assert abs(823.0 - x) < 10.0 and abs(1053.0 - y) < 10.0

    # sub-optimal click in region
    # "padding" behavior pushes the Y out of the intended region
    effect.intended_region = (0, 0, 603, 914)
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    x, y = device.last_args
    assert abs(319.0 - x) < 10.0 and abs(1053.0 - y) < 10.0


def test_ClickSubimageNearestEffect():
    device = MockDevice()

    effect = ClickSubimageNearestEffect(match_path=TESTDATA_COND + "button.png",
                                        click_path=TESTDATA_COND + "button.png", validator=None)
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    x, y = device.last_args
    assert abs(823.0 - x) < 10.0 and abs(1053.0 - y) < 10.0

    effect = ClickSubimageNearestEffect(match_path=TESTDATA_COND + "button.png",
                                        click_path=TESTDATA_COND + "nearest_click.png", validator=None)
    effect.apply(Image.open(TESTDATA_COND + "nearest_search.png"), {}, {"device": device})
    device.print()
    x, y = device.last_args
    assert abs(551.0 - x) < 10.0 and abs(852.0 - y) < 10.0

    effect = ClickSubimageNearestEffect(match_path=TESTDATA_COND + "button.png",
                                        click_path=TESTDATA_COND + "nearest_click.png",
                                        validator=validator_common_horizontal_range)
    effect.apply(Image.open(TESTDATA_COND + "nearest_search.png"), {}, {"device": device})
    device.print()
    x, y = device.last_args
    assert abs(802.0 - x) < 10.0 and abs(560.0 - y) < 10.0

    effect = ClickSubimageNearestEffect(match_path=TESTDATA_COND + "button.png",
                                        click_path=TESTDATA_COND + "nearest_click.png",
                                        validator=validator_common_vertical_range)
    effect.apply(Image.open(TESTDATA_COND + "nearest_search.png"), {}, {"device": device})
    device.print()
    x, y = device.last_args
    assert abs(69.0 - x) < 10.0 and abs(1031.0 - y) < 10.0


def test_ClickSubimageNearestEffectValidators():
    box_a = [10, 10, 10, 10]
    assert validator_common_horizontal_range(box_a, [5, 20, 10, 10])  # overlap
    assert validator_common_horizontal_range([5, 20, 10, 10], box_a)
    assert validator_common_horizontal_range(box_a, [0, 20, 20, 10])  # contains
    assert validator_common_horizontal_range([0, 20, 20, 10], box_a)
    assert not validator_common_horizontal_range(box_a, [0, 20, 5, 0])

    assert validator_common_vertical_range(box_a, [20, 5, 10, 10])  # overlap
    assert validator_common_vertical_range([20, 5, 10, 10], box_a)
    assert validator_common_vertical_range(box_a, [20, 0, 10, 20])  # contains
    assert validator_common_vertical_range([20, 0, 10, 20], box_a)
    assert not validator_common_vertical_range(box_a, [0, 20, 5, 0])


def test_ClickRelativeRegionEffect():
    device = MockDevice()

    effect = ClickRelativeRegionEffect(scene_image_path=TESTDATA_COND + "contained.png",
                                       click_image_path=TESTDATA_COND + "button.png")
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    x, y = device.last_args
    assert abs(823.0 - x) < 10.0 and abs(1053.0 - y) < 10.0


def test_DragSubimageEffect():
    device = MockDevice()
    effect = DragSubimageEffect(image_path=TESTDATA_COND + "button.png", intended_region=None,
                                tap_coords_in_image=[0, 0], movement_amount=[5, 5], duration=5)
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    assert device.last_args == [721, 1026, 726, 1031, 5]

    device = MockDevice()
    effect = DragSubimageEffect(image_path=TESTDATA_COND + "nearest_click.png", intended_region=[600, 100, 1000, 400],
                                tap_coords_in_image=[0, 0], movement_amount=[5, 5], duration=5)
    effect.apply(Image.open(TESTDATA_COND + "nearest_search.png"), {}, {"device": device})
    assert device.last_args == [751, 209, 756, 214, 5]


def test_ScrollRegionEffect():
    device = MockDevice()
    effect = ScrollRegionEffect(image_path=TESTDATA_COND + "button.png", start="left", end="right")
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    assert device.last_args == [721, 1055, 825, 1055, 0]

    effect = ScrollRegionEffect(image_path=TESTDATA_COND + "button.png", start="top", end="bottom")
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    device.print()
    assert device.last_args == [825, 1026, 825, 1084, 0]


def test_ScrollRelativeRegionEffect():
    device = MockDevice()
    effect = ScrollRelativeRegionEffect(scroll_image_path=TESTDATA_COND + "button.png", scene_image_path=TESTDATA_COND + "contained.png", start="left", end="right")
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    assert device.last_args == [721, 1055, 825, 1055, 0]

    effect = ScrollRelativeRegionEffect(scroll_image_path=TESTDATA_COND + "button.png", scene_image_path=TESTDATA_COND + "contained.png", start="top", end="bottom")
    effect.apply(Image.open(TESTDATA_COND + "contained.png"), {}, {"device": device})
    device.print()
    assert device.last_args == [825, 1026, 825, 1084, 0]
