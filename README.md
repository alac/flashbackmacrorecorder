# FlashbackMacroRecorder

FlashbackMacroRecorder is a tool that allows you to record and playback macros on Windows applications. It uses image data and basic computer vision to recover in scenarios with variable lag and to add branching behaviors to macros.

This is particularly useful for Android applications being run through Windows.

FBMR can be used for:
* Automating repetitive tasks, like QA workflows.
* Building apps that perform complex UI interactions, e.g. a bot that takes community input to perform actions in a game like 'twitchplayspokemon'.

## Features

* Records mouse clicks and drag events along with image data, timings, and positional data.
* Can playback macros with the correct timing even if the application is lagging or if there is a network delay.
* Can add branching behaviors to macros by using image data to identify different states of the application.
* Supports Android applications that can be run on Windows (via ADB, Bluestacks, or Scrcpy).

## Limitations

* Only supports left clicks and drags on Windows applications.
* Supported Windows applications vary based on how the application is rendered. 

## Installation

Install python if you don't have it; tested on 3.10.

1. Clone the GitHub repository:

```
git clone https://github.com/alac/flashbackmacros.git
```

2. Install the dependencies:

```
pip install -r requirements.txt
```

3. (For Android automation) Setup ADB Debugging.

If you plan on using this with an Android device or an emulator like Bluestacks. Turn on ADB Debugging.
On Bluestacks, you would go to `Settings` -> `Advanced` -> `Enable ADB`
With an Android device, you're likely going to use `scrcpy`. Head over there for the [instructions](https://github.com/Genymobile/scrcpy#prerequisites).


## Usage
1. Set up your settings.txt and devices. [link](docs/settings_device_configs.md)
2. Record a macro. [link](docs/macro_recording.md)
3. Run the macro.
```
python -m tools.runner [config name] [device name] --ui
```
This runs the macro with default settings a user interface with live screenshots and logging.

If you run into issues, check out [debugging](docs/debugging.md)

For advanced behaviors like branching, check out [advanced usage](docs/advanced_usage.md)

## Future Work

* Add a scheduler to run macros on a user-defined schedule.
* Add a graph visualizer for the flow of a FlashbackMacro.
* Integrate image segmentation and object detection.
* Add an HTTP server so that FlashbackMacros can interface with non-Python applications.
* Add support for right clicks and keyboard actions on Windows applications.

## Errata

Test are standard pytest fare.
Run them with `pytest .\tests`.

## Related/Thanks

This project leverages several libraries for the Android side of things.

[https://github.com/leng-yue/py-scrcpy-client](https://github.com/leng-yue/py-scrcpy-client)

[https://github.com/Genymobile/scrcpy](https://github.com/Genymobile/scrcpy)

[https://github.com/openatx/adbutils](https://github.com/openatx/adbutils)
