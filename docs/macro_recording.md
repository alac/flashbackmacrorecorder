## Recording a Macro

To record a macro, you can use the `macro_recorder_ui` script.

1. Open a terminal window and navigate to the FlashbackMacros directory.
2. Run the following command:

```
python -m tools.macro_recorder_ui
```

This script will open a graphical user interface that allows you to select the device, config, and action name for your macro.

Once you have selected the desired options, click the "Start" button to begin recording. The macro recorder will not start recording until you click in the window. All other clicks will be ignored.

The macro recorder will create a new config folder in the `configs` directory. This folder will contain the image data, timings, and positional data for each click in the macro.

To stop recording, click the "Stop" button or press `Ctrl`+`C`.

Tips for recording a reliable macro:

* Wait for animations to finish between clicks. Otherwise, you may get the wrong image recorded.
* If two successive actions look identical (e.g. clicking the same "OK" button on two different popups), you can add an extra click to separate the first and the second (e.g. clicking "OK" then the title of the second popup then clicking the "OK" button).