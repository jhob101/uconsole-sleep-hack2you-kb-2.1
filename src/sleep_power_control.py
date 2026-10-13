import os
import time
import inotify.adapters
import inotify.constants

# from find_drm_panel import find_drm_panel
from find_backlight import find_backlight
from find_internal_kb import find_internal_kb

SAVING_CPU_FREQ = os.environ.get("SAVING_CPU_FREQ")
DISABLE_POWER_OFF_KB = os.environ.get("DISABLE_POWER_OFF_KB") == "yes"
DISABLE_CPU_MIN_FREQ = os.environ.get("DISABLE_CPU_MIN_FREQ") == "yes"


# The bb9900 ZMK firmware (hack2you v2.1) holds its trackpad light off while the
# host has the Kana LED on. Unbinding doesn't cut the keyboard's power, so this
# is the only way to put the light out.
TRACKPAD_LIGHT_KB_ID = "1d50:615e"
LED_REPORT_ID = 1
LED_BITS = {"numlock": 0x01, "capslock": 0x02, "scrolllock": 0x04, "compose": 0x08}
KANA_BIT = 0x10


def find_kb_hidraw():
    # The HID device is recreated on every bind, so look it up each time.
    for root, dirs, _ in os.walk(kb_device_path):
        if os.path.basename(root) == "hidraw" and dirs:
            return os.path.join("/dev", dirs[0])
    return ""


def kb_led_bits():
    # Keep the other LEDs as the kernel has them, so only Kana changes.
    bits = 0
    for root, dirs, _ in os.walk(kb_device_path):
        for d in dirs:
            name = d.rpartition("::")[2]
            if name in LED_BITS:
                with open(os.path.join(root, d, "brightness"), "r") as f:
                    if f.read().strip() != "0":
                        bits |= LED_BITS[name]
    return bits


def set_kb_kana(on, wait_sec=0):
    if kb_vid_pid != TRACKPAD_LIGHT_KB_ID:
        return

    deadline = time.monotonic() + wait_sec
    hidraw_path = find_kb_hidraw()
    while not hidraw_path and time.monotonic() < deadline:
        time.sleep(0.1)
        hidraw_path = find_kb_hidraw()
    if not hidraw_path:
        print("kb kana led: hidraw not found")
        return

    # Writing the LED report to hidraw goes out as a SET_REPORT control
    # transfer and returns once the keyboard has it. Writing the LED's sysfs
    # brightness instead is queued, and an unbind straight after could drop it.
    bits = kb_led_bits() | (KANA_BIT if on else 0)
    with open(hidraw_path, "wb", buffering=0) as f:
        f.write(bytes([LED_REPORT_ID, bits]))
    print(f"kb kana led: {'on' if on else 'off'}")


def control_by_state(state):
    global kb_device_path
    global kb_device_id
    global usb_driver_path
    global cpu_policy_path

    if state:
        if not DISABLE_CPU_MIN_FREQ:
            with open(os.path.join(cpu_policy_path, "scaling_max_freq"), "w") as f:
                f.write(default_cpu_freq_max)
            print(f"cpu freq max: {default_cpu_freq_max}")
            with open(os.path.join(cpu_policy_path, "scaling_min_freq"), "w") as f:
                f.write(default_cpu_freq_min)
            print(f"cpu freq min: {default_cpu_freq_min}")
        if not DISABLE_POWER_OFF_KB:
            with open(os.path.join(usb_driver_path, "bind"), "w") as f:
                f.write(kb_device_id)
            print("kb power state: bind")
        with open(os.path.join(kb_device_path, "power/control"), "w") as f:
            f.write("on")
        set_kb_kana(False, wait_sec=3)
    else:
        set_kb_kana(True)
        if DISABLE_POWER_OFF_KB:
            # Only set autosuspend when not unbinding — unbinding handles power-off
            # and writing "auto" with autosuspend_delay_ms=0 before unbind triggers
            # a failed USB suspend (EPROTO, error -71).
            with open(os.path.join(kb_device_path, "power/control"), "w") as f:
                f.write("auto")
        else:
            with open(os.path.join(usb_driver_path, "unbind"), "w") as f:
                f.write(kb_device_id)
            print("kb power state: unbind")
        if not DISABLE_CPU_MIN_FREQ:
            with open(os.path.join(cpu_policy_path, "scaling_min_freq"), "w") as f:
                f.write(saving_cpu_freq_min)
            print(f"cpu freq min: {saving_cpu_freq_min}")
            with open(os.path.join(cpu_policy_path, "scaling_max_freq"), "w") as f:
                f.write(saving_cpu_freq_max)
            print(f"cpu freq max: {saving_cpu_freq_max}")


backlight_path = find_backlight()
# drm_panel_path = find_drm_panel()
kb_device_path = find_internal_kb()
kb_device_id = os.path.basename(kb_device_path)
usb_driver_path = "/sys/bus/usb/drivers/usb"
cpu_policy_path = "/sys/devices/system/cpu/cpufreq/policy0"

if not backlight_path:
    raise Exception("there's no matched backlight")

# if not drm_panel_path:
#    raise Exception("there's no matched drm panel")

if not kb_device_path:
    raise Exception("there's no matched kb")

with open(os.path.join(kb_device_path, "idVendor"), "r") as f:
    kb_vid_pid = f.read().strip()
with open(os.path.join(kb_device_path, "idProduct"), "r") as f:
    kb_vid_pid += ":" + f.read().strip()

with open(os.path.join(kb_device_path, "power/autosuspend_delay_ms"), "w") as f:
    f.write("0")
    print(f"{kb_device_path}/power/autosuspend_delay_ms = 0")

if not SAVING_CPU_FREQ:
    with open(os.path.join(cpu_policy_path, "cpuinfo_min_freq"), "r") as f:
        saving_cpu_freq_min = f.read().strip()
        saving_cpu_freq_max = saving_cpu_freq_min
else:
    saving_cpu_freq_min, saving_cpu_freq_max = SAVING_CPU_FREQ.split(",")
    saving_cpu_freq_min = f"{saving_cpu_freq_min}000"
    saving_cpu_freq_max = f"{saving_cpu_freq_max}000"
print(f"saving_cpu_freq_min: {saving_cpu_freq_min}")
print(f"saving_cpu_freq_max: {saving_cpu_freq_max}")

with open(os.path.join(cpu_policy_path, "scaling_min_freq"), "r") as f:
    default_cpu_freq_min = f.read().strip()
    print(f"default_cpu_freq_min: {default_cpu_freq_min}")

with open(os.path.join(cpu_policy_path, "scaling_max_freq"), "r") as f:
    default_cpu_freq_max = f.read().strip()
    print(f"default_cpu_freq_max: {default_cpu_freq_max}")

backlight_bl_path = os.path.join(backlight_path, "bl_power")
with open(backlight_bl_path, "r") as f:
    screen_state = f.read().strip()

# drm_enabled_path = os.path.join(drm_panel_path, "enabled")
# with open(drm_enabled_path, "r") as f:
#    screen_state = f.read().strip()

try:
    control_by_state(screen_state != "4")
#    control_by_state(screen_state != "disabled")
except Exception as e:
    print(f"Error occurred: {e}, on init. ignored")

i = inotify.adapters.Inotify()
i.add_watch(backlight_bl_path, mask=inotify.constants.IN_MODIFY)

print(f"Monitoring {backlight_bl_path} for changes...")

last_screen_state = ""
while True:
    try:
        list(i.event_gen(yield_nones=False, timeout_s=1))

        with open(backlight_bl_path, "r") as f:
            screen_state = f.read().strip()

        if screen_state == last_screen_state:
            continue
        last_screen_state = screen_state

        control_by_state(screen_state != "4")

    except Exception as e:
        print(f"Error occurred: {e}")
