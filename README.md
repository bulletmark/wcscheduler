## WCSCHEDULER - Schedule Watts Clever Switches

This is a Raspberry Pi program to switch one or more Watts Clever RF
Switches on or off at specified times and days of week. It uses my
[Python module `wcccontrol`](https://github.com/bulletmark/wccontrol)
which controls Watts Clever switches via an RF transmitter.

The latest version of this document and code is available at
https://github.com/bulletmark/wcscheduler.

### Installation

```bash
git clone https://github.com/bulletmark/wcscheduler.git
cd wcscheduler
python3 -m venv env
env/bin/pip install -r requirements.txt
env/bin/pip install wcscheduler
```

The above will install
[`wccontrol`](https://github.com/bulletmark/wccontrol/) in your local env/
dir but you then need to follow the instructions to [make the GPIO
accessible](https://github.com/bulletmark/wccontrol#make-gpio-device-accessible) and then to [program the switches](https://github.com/bulletmark/wccontrol#groups-and-addresses).

Be sure to set up the `gpio` group and `udev` rules etc as described and
also program the switch groups and addresses. Run `env/bin/wccontrol`
from within your `wcscheduler` dir to program the switches.

### Configuration

Copy the sample [`wcscheduler.conf`](https://github.com/bulletmark/wcscheduler/blob/master/wcscheduler.conf)
configuration file to `~/.config/wcscheduler.conf` and then edit the
sample settings to your requirements. You can add multiple timers for
multiple devices as described by the comments in that file.

### Systemd Configuration for Auto Start etc

Copy the included
[`wcscheduler.service`](https://github.com/bulletmark/wcscheduler/blob/master/wcscheduler.service)
to `/etc/systemd/systemd/` and edit the `#TEMPLATE#` values within. Then:

    sudo systemctl enable wcscheduler
    sudo systemctl start wcscheduler

If you change the configuration then restart with:

    sudo systemctl restart wcscheduler

To see status and logs:

    systemctl status wcscheduler
    journalctl -u wcscheduler

### Command Line Usage

```
usage: wcscheduler [-h] [-c CONFIG]

Program to schedule control of Watts Clever switches

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        alternative configuration file
```

<!-- vim: se ai syn=markdown: -->
