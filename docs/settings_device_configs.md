# Settings and Devices

## Settings
Global settings are available in settings.toml.

Settings are loaded once at launch, so you'll need to restart FBMR to get updated settings.

## Devices
Devices are configured via .toml files in the `/devices` folder.

There are examples in `/devices/examples` with comments on how to fill each out.

You'll want a `device` configuration for each device you want to automate. The types are:

- `WindowsAppDevice` which automates Windows Apps. Support is spotty because of the variety of ways a Windows App can be rendered.
- `WindowsAndroidDevice` which automates Android phones through a Windows App (e.g. an emulator like Bluestacks or a screen mirroring app like Scrcpy).
- `StreamingAndroidDevice` which automates Android phones through USB.
   - To record the macro with MacroRecorder, you'll want to mirror the Android phone with Scrcpy and use a `WindowsAndroidDevice` for the Scrcpy window.
