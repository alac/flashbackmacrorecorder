from PIL import Image

from fbmr.conditions import SubimageCondition, NotSubimageCondition

TESTDATA_ROOT = "tests/test_data_conditions/"


def test_subimage_condition():
    condition = SubimageCondition(
        TESTDATA_ROOT + "button.png", None, 80, 1.0, save_region_as="button"
    )

    # test jsonification
    json_data = condition.make_json()
    condition2 = SubimageCondition.load(json_data)
    json_data2 = condition2.make_json()
    for key in json_data:
        assert json_data[key] == json_data2[key]

    state_dict = {}
    assert (
        condition.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        > 0
    )
    location = state_dict["button"]
    assert (
        condition.is_valid(
            Image.open(TESTDATA_ROOT + "not_contained.png"), state_dict, {}
        )
        == 0
    )

    condition.intended_region = (603, 914, 603 + 503, 914 + 346)
    location2 = state_dict["button"]
    assert (
        condition.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        > 0
    )
    assert location2 == location

    condition.intended_region = (0, 0, 0 + 503, 0 + 346)
    assert (
        condition.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        == 0
    )

    state_dict = {}
    assert (
        condition2.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        > 0
    )
    location = state_dict["button"]
    assert (
        condition2.is_valid(
            Image.open(TESTDATA_ROOT + "not_contained.png"), state_dict, {}
        )
        == 0
    )

    condition2.intended_region = (603, 914, 603 + 503, 914 + 346)
    location2 = state_dict["button"]
    assert (
        condition2.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        > 0
    )
    assert location2 == location

    condition2.intended_region = (0, 0, 0 + 503, 0 + 346)
    assert (
        condition2.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        == 0
    )


def test_not_subimage_condition():
    condition = NotSubimageCondition(
        TESTDATA_ROOT + "button.png", None, 80, 1.0, save_region_as="button"
    )

    # test jsonification
    json_data = condition.make_json()
    condition2 = NotSubimageCondition.load(json_data)
    json_data2 = condition2.make_json()
    for key in json_data:
        assert json_data[key] == json_data2[key]

    state_dict = {}
    assert (
        condition.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        == 0
    )
    assert (
        condition.is_valid(
            Image.open(TESTDATA_ROOT + "not_contained.png"), state_dict, {}
        )
        != 0
    )

    condition.intended_region = (603, 914, 603 + 503, 914 + 346)
    assert (
        condition.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        == 0
    )

    condition.intended_region = (0, 0, 0 + 503, 0 + 346)
    assert (
        condition.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        != 0
    )

    state_dict = {}
    assert (
        condition2.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        == 0
    )
    assert (
        condition2.is_valid(
            Image.open(TESTDATA_ROOT + "not_contained.png"), state_dict, {}
        )
        != 0
    )

    condition2.intended_region = (603, 914, 603 + 503, 914 + 346)
    assert (
        condition2.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        == 0
    )

    condition2.intended_region = (0, 0, 0 + 503, 0 + 346)
    assert (
        condition2.is_valid(Image.open(TESTDATA_ROOT + "contained.png"), state_dict, {})
        != 0
    )
