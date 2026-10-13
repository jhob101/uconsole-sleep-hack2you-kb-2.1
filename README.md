# uConsole-sleep v1.5
### Sleep Service Package for uConsole

> This fork adds support for the **hack2you v2.1 keyboard** (BlackBerry 9900
> keyboard and trackpad, USB ID `1d50:615e`), and puts its trackpad light out
> while the screen is off. See [hack2you v2.1 keyboard](#hack2you-v21-keyboard).
> The original project is [qkdxorjs1002/uConsole-sleep](https://github.com/qkdxorjs1002/uConsole-sleep).

This service is built for **Ubuntu 22.04** and implemented in **Python**.

It monitors power key events and controls the screen power (on/off).  
Initially, power key events were detected using a polling loop, but this was later replaced with **epoll** to reduce CPU usage.

When the screen turns off for any reason (e.g., screensaver activation, desktop lock, or system sleep), the service detects the screen-off state and applies several power-saving measures:

- Sets the CPU maximum frequency to the minimum
- Disables power to the built-in keyboard
- Disables the keyboard wakeup trigger
- Switches off the hack2you v2.1 keyboard's trackpad light

I also experimented with switching the CPU governor to `powersave`, but observed a slight delay during state transitions, so the current implementation adjusts the maximum CPU frequency instead.

Similarly, screen-off detection was originally implemented using a polling loop, but it was replaced with **inotify** to further reduce CPU load.

## Components

The service consists of two background processes:

### sleep-remap-powerkey
`/usr/local/bin/sleep_remap_powerkey`

Detects power key events and controls the screen power state.

### sleep-power-control
`/usr/local/bin/sleep_power_control`

Handles power-saving behavior based on the current screen state.

### sleep_display_control
`/usr/local/bin/sleep_display_control` (shared library used by both services)

Manages DRM/framebuffer display power and backlight control.

## How to package and install

Install dependencies first:

```
sudo apt install python3-inotify python3-uinput
```

Build and install the package:

```
ENV_VERSION=1.5 ./make_uconsole-sleep_package.sh
sudo dpkg -i uconsole-sleep.deb
```

## Service management

```
# Enable and start services (done automatically on install)
sudo systemctl enable sleep-remap-powerkey sleep-power-control
sudo systemctl start sleep-remap-powerkey sleep-power-control

# Check status
systemctl status sleep-remap-powerkey
systemctl status sleep-power-control

# View logs
journalctl -u sleep-remap-powerkey -f
journalctl -u sleep-power-control -f

# Stop and disable
sudo systemctl stop sleep-remap-powerkey sleep-power-control
sudo systemctl disable sleep-remap-powerkey sleep-power-control
```

## Configuration

Configuration file: `/etc/uconsole-sleep/config`

| Option | Default | Description |
|---|---|---|
| `HOLD_TRIGGER_SEC` | `0.7` | Hold duration (seconds) to trigger power interactive menu |
| `SAVING_CPU_FREQ` | `100,100` | CPU frequency (MHz) `<min,max>` applied during power saving |
| `DISABLE_POWER_OFF_DRM` | `no` | Disable turning off DRM on sleep (set `yes` if screen recovery has issues) |
| `DISABLE_POWER_OFF_KB` | `no` | Disable turning off keyboard on sleep (set `yes` to allow keyboard to control its backlight) |
| `DISABLE_CPU_MIN_FREQ` | `no` | Disable setting CPU max frequency to minimum during sleep |

## hack2you v2.1 keyboard

The keyboard is detected like the official one, and unbound on sleep. Unbinding
doesn't cut its power, though, so on its own the trackpad light would stay on
with the screen off.

To put the light out, `sleep_power_control` switches the keyboard's Kana LED on
just before unbinding it, and off again once it is bound on wake. The keyboard
firmware holds the trackpad light off while Kana is on. The LED report is
written straight to the keyboard's `/dev/hidraw*` device, which returns once
the keyboard has it, so the unbind can't overtake it. This is only done for
`1d50:615e`; other keyboards are left alone.

This needs firmware that understands the Kana signal:
[jhob101/uconsole-bb9900-keyboard](https://github.com/jhob101/uconsole-bb9900-keyboard),
built from [jhob101/zmk](https://github.com/jhob101/zmk) (option
`CONFIG_ZMK_TRACKPAD_LIGHT_HOST_SLEEP`, on by default). Older firmware ignores
it and the light just stays on as before. The light stays off after waking if
the keyboard is locked with Fn+Esc, until it is unlocked.

If the light doesn't go out, check the log for `kb kana led: on` before
`kb power state: unbind`:

```
journalctl -u sleep-power-control -f
```

## More Information

Discussion and updates are available on the ClockworkPi forum:  
https://forum.clockworkpi.com/t/uconsole-sleep-v1-2/15612?u=paragonnov

---

<a href="https://www.buymeacoffee.com/paragonnov" target="_blank">
<img src="https://cdn.buymeacoffee.com/buttons/v2/default-red.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;">
</a>
