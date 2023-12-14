# Debugging

This section provides suggestions on what to do when your FlashbackMacro is failing to run.

If you are having problems with your macro, you can use the following steps to debug it:

1. Check the console log, which will show which actions executed and the information on attempts to match images to screenshots.
2. Look at the images in the `configs/` directory. These images are used to match the current state of the application to the state that was recorded in the macro.
3. If the image match is failing, you can try the following:
    * Make sure that the click region is still the same.
    * Add a branching condition to the macro to account for different states of the application.
    * Reduce the threshold for the image match.

The sections below provide more detail on each step.

## Checking the log file
Information about every attempt to match an action to the application state is saved to the most recent file in the /logs folder.

For example, if the macro is trying to click a button and the button is not found, the console log will contain an error message like:

```
Checking action click_button_1: starting
SubimageCondition match (ADJUSTED_MATCH_STRENGTH/MINIMUM_SCORE) for IMAGE_NAME
Checking action click_button_1: final score XYZ
```

In this example, the `click_button_1` action is failing because the image match is not strong enough.

The ADJUSTED_MATCH_STRENGTH is a number from 0 to 100. By default, it's `100*MATCH_STRENGTH`. If this number is below the threshold of MINIMUM_SCORE (default 70), the action will fail.

In general, the most important piece of information is the IMAGE_NAME since checking the image is the best way to determine the cause of failure.

## Checking the source images

The images in the `configs/YOURMACRO/` directory are used to match the current state of the application to the state that was recorded in the macro. Each image is named after the action that it is associated with. For example, the image for the `click_button_1` action would be prefixed `click_button_1`.

If the image match is failing, you can try opening the image in an image editor and comparing it to the current state of the application. If the two images are not the same, you can try to adjust the click region or add a branching condition to the macro.

## Changing the match threshold

You can try reducing the match threshold if the image looks close to the state of the application, but varies subtly (e.g. it has subtle animation, like a moving background).

Reducing the threshold for the image match will make it easier for the macro to find a match. However, this can also make the macro more likely to match a different area of the screen. Therefore, it is important to test the macro carefully after reducing the threshold.