# Advanced Usage

FlashbackMacros can support branching behaviors based on the visual state of the application. This can be achived by editing `config.json` or writing a custom script.

## Branching in config.json

You can add branching to your macros by editing the `config.json` file. Each action in the `config.json` file can have a list of next action names. When the macro reaches an action, it will check the list of next action names and choose one to execute.

For example, the following `config.json` file defines a macro with two branches:

```
{
  "actions": [
    {
      "name": "click_gamble",
      "next_action_names": ["result_win", "result_lose"]
    },
    {
      "name": "result_win",
      "next_action_names": ["result_winnings"]
    },
    {
      "name": "result_lose",
      "next_action_names": ["click_gamble"]
    }
  ]
}
```

This macro has three actions: `click_gamble`, `result_win`, and `result_lose`. After the macro performs the `click_gamble` action, it will check the list of next action names and choose one to execute based on the visual state of the app. In this example, the macro branches to handle the win and loss scenarios.


## Custom Runners Script

You can also write a custom runner to run your macro in a different way. The default runner, `Runner`, simply executes the actions in the `config.json` file in order. However, you could write a custom runner to do things like:

* Choose the next action based on the result of a previous action.
* Adding custom logging, saving screenshots or other behaviors like making HTTP requests.
* Retry failed actions.
* Terminate the macro on certain conditions.

To write a custom runner, you can use the `Executor` class. The `Executor` class has methods for executing actions, pausing the macro, resuming the macro, retrying failed actions, and terminating the macro.


### Example: Runner with timeout
This runner takes a timeout argument, which specifies the maximum runtime of the macro in minutes. If the macro does not finish running within the timeout period, the runner will stop the macro and exit.
```
from tools.runner import Runner
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(dest='timeout', type=float, help="Maximum runtime in minutes")
args = parser.parse_args()

r = Runner(config_name="CONFIG_NAME", device_name="DEVICE_NAME")
r.run(next_actions=["click_1"], exit_actions=["click_5"], min_action_delay=1, state = {"viability_adjustment": 10}, max_minutes=args.timeout)
```
The `Runner` will return control to the caller when:
1. It reaches an empty `next_action_names`
2. It performs an action in `exit_actions`
3. The total runtime reaches the value provided in the optional `max_minutes` argument.

If you provide a non-empty `exit_actions` and the script cannot reach it, it will throw `UnreachableExitActionException`.


### Example: Using FlashbackMacros APIs
This is a script that uses FlashbackMacros launch an app and dismiss an optional modal.
```
from fbmr.devices import all_device_constructors
from fbmr.config import Config
from fbmr.executor import Executor

config = Config("configs", "MyApp_DismissModal")
executor = Executor()
executor.set_config(config)
device = all_device_constructors()["ANDROID_DEVICE_NAME"]()
utils = {"device": device}

# kill the app if it was already open and recompute the window size in case orientation changed
device.close_app(BUNDLE_ID)
device.open_app(BUNDLE_ID)
device.recompute_size(delay=5)
# launch the app and click the prompts until you get to the homescreen
executor.execute_chain("launch_app_1", ["launch_app_4"], state, utils, min_action_delay=delay)

# dismiss modal
image = device.screen_capture()
action = config.get_action("dismiss_modal_1")
viability = executor.check_conditions(action.conditions, f"Checking for modal", image, state, utils)
if viability != 0:
	executor.execute_chain("dismiss_modal_1", ["dismiss_modal_3"], state, utils, min_action_delay=delay)
...
```
