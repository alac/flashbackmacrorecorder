"""
detect_subimage.py

methods for detecting an image within a bigger image + debugging.
"""

import datetime
import logging
import ntpath
import os
from pathlib import Path

import cv2
import numpy as np

from fbmr.utils.debug_settings import debug_settings

GLOBAL_INCREMENT = 0


def check_file_exists(fp):
    if not os.path.exists(fp):
        raise ValueError(f"File not found: {fp}")


def find_location_path(object_path, scene_path):
    """
    _find_location handles the task of finding the location of an object
    in a scene (in CV terms: a template in a source).

    find_location calls into this and has useful debugging behaviors.

    returns (strength, (x,y, width, height))
      strength = 0 to 1, the quality of the match.
        low is good for SQ_DIFF, high is good for all others.
      x/y/width/height = obvious.
    """
    check_file_exists(object_path)
    check_file_exists(scene_path)
    template = cv2.imread(object_path)
    source = cv2.imread(scene_path)
    return find_location_cv(template, source)


def find_location_pil(template_pil_img, scene_pil_img):
    return find_location_cv(
        cv2.cvtColor(np.array(template_pil_img), cv2.COLOR_RGB2BGR),
        cv2.cvtColor(np.array(scene_pil_img), cv2.COLOR_RGB2BGR),
    )


def find_location_path_pil(object_path, scene_pil_img):
    check_file_exists(object_path)
    return find_location_cv(
        cv2.imread(object_path),
        cv2.cvtColor(np.array(scene_pil_img), cv2.COLOR_RGB2BGR),
        template_name=os.path.splitext(ntpath.basename(object_path))[0]
    )


def find_location_multi_path_pil(object_path, scene_pil_img, threshold):
    check_file_exists(object_path)
    return find_location_cv_multi(
        cv2.imread(object_path),
        cv2.cvtColor(np.array(scene_pil_img), cv2.COLOR_RGB2BGR),
        threshold,
        template_name=os.path.splitext(ntpath.basename(object_path))[0]
    )


def find_location_cv(template_cvimg, scene_cvimg, template_name="UNKNOWN"):
    matches = find_location_cv_multi(template_cvimg, scene_cvimg, template_name=template_name)
    assert len(matches) > 0
    return matches[0]


def find_location_cv_multi(template_cvimg, scene_cvimg, threshold=.5, min_count=1, max_count=10,
                           template_name="UNKNOWN"):
    # Check for valid input; openCV's assertion for this isn't very clear
    t_height, t_width, t_channels = template_cvimg.shape
    s_height, s_width, s_channels = scene_cvimg.shape
    assert t_height > 0, "template image shouldn't be empty"
    assert t_width > 0, "template image shouldn't be empty"
    assert s_height > 0, "scene image shouldn't be empty"
    assert s_width > 0, "scene image shouldn't be empty"

    result = cv2.matchTemplate(scene_cvimg, template_cvimg, cv2.TM_CCOEFF_NORMED)
    h, w = template_cvimg.shape[:2]

    strengths_and_bounding_boxes = []
    count = 0
    while count < max_count:
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if count >= min_count and max_val < threshold:
            break
        x, y = max_loc
        strengths_and_bounding_boxes.append((max_val, (x, y, t_width, t_height)))
        logging.getLogger("fbmr_logger").debug("template_matching (str {}) at x,y ({}, {}) with size ({}, {})".format(
                max_val, x, y, w, h))
        result[max_loc[1] - h // 2:max_loc[1] + h // 2 + 1, max_loc[0] - w // 2:max_loc[0] + w // 2 + 1] = 0
        count += 1

    if debug_settings.save_detect_subimage_images:
        for strength, box in strengths_and_bounding_boxes:
            write_debug_image(scene_cvimg, strength, [box], template_name=template_name)

    return strengths_and_bounding_boxes


def write_debug_image(scene_cvimg, strength, bounding_boxes, template_name="UNKNOWN",
                      debug_image_folder=debug_settings.debug_folder, debug_image_name=None, display_window=False):
    if debug_image_folder is None and display_window is False:
        return

    source = scene_cvimg
    for bounding_box in bounding_boxes:
        x, y, width, height = bounding_box
        cv2.rectangle(source, (x, y), (x + width, y + height), (255, 0, 0))

    if debug_image_name is None and debug_image_folder is not None:
        template_name = template_name
        # Year Month Day DayOfWeek Time
        timestamp = datetime.datetime.now().strftime("%Y %B %d %A %I-%M-%S%p")
        global GLOBAL_INCREMENT
        debug_image_name = f"{timestamp} - search #{GLOBAL_INCREMENT} for {template_name}.png"
        GLOBAL_INCREMENT += 1

    if debug_image_folder and debug_image_name and debug_settings.save_detect_subimage_images:
        path = Path(debug_image_folder)
        path.mkdir(parents=True, exist_ok=True)

        debug_image_path = os.path.join(debug_image_folder, debug_image_name.replace(
            ".png", " {}.png".format(str(strength)[:4])))

        if debug_settings.log_detect_subimage:
            debug_settings.detect_subimages_logger(f"template_matching saving image {debug_image_path}")
        cv2.imwrite(debug_image_path, source)

    if display_window:
        cv2.namedWindow('Source', cv2.WINDOW_AUTOSIZE)
        cv2.imshow('Source', source)
        cv2.waitKey(0)
        cv2.destroyWindow('Source')

    return


def pad_region(intended_region, image_size):
    """extends boundaries of a region (x1,y1,x2,y2)"""
    c_l, c_t, c_r, c_b = intended_region
    w = c_r - c_l
    h = c_b - c_t
    max_x, max_y = image_size

    if c_r > max_x or c_b > max_y:
        raise ValueError(f"intended region contains point {(c_r, c_b)} outside of" + \
            "image {(image_size)}")

    c_l = int(c_l - .25 * w)
    c_r = int(c_r + .25 * w)
    c_t = int(c_t - .25 * h)
    c_b = int(c_b + .25 * h)
    c_l = max(0, c_l)
    c_r = min(max_x, c_r)
    c_t = max(0, c_t)
    c_b = min(max_y, c_b)
    return c_l, c_t, c_r, c_b
