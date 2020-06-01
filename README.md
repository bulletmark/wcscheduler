## WCSCHEDULER - Schedule Watts Clever Switches

This is a Raspberry Pi program to switch one or more Watts Clever RF
switches to turn mains powered devices on or off at specified times and
days of week. It uses my Python module
[`wcccontrol`](https://github.com/bulletmark/wccontrol) which controls
Watts Clever switches via an RF transmitter. It also runs a small
internal webserver to receive webhooks commands from the internet, e.g.
from [IFTTT](https://ifttt.com/) using Google Assistant, to remotely
switch the devices.

The latest version of this document and code is available at
https://github.com/bulletmark/wcscheduler.

### Installation

Requires Python 3.4 or later. Does not work with Python 2.

```bash
git clone https://github.com/bulletmark/wcscheduler.git
cd wcscheduler
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

The above will install
[`wccontrol`](https://github.com/bulletmark/wccontrol/) in your local `venv/`
dir but you then need to follow the instructions to [make the GPIO
accessible](https://github.com/bulletmark/wccontrol#make-gpio-device-accessible) and then to [program the switches](https://github.com/bulletmark/wccontrol#groups-and-addresses).

Be sure to set up the `gpio` group and `udev` rules etc as described and
also program the switch groups and addresses. Run `venv/bin/wccontrol`
from within your `wcscheduler` dir to program the switches.

### Configuration

Copy the sample
[`wcscheduler.conf`](https://github.com/bulletmark/wcscheduler/blob/master/wcscheduler.conf)
configuration file to `~/.config/wcscheduler.conf` and then edit the
sample settings in that target file to your requirements. You can add
multiple timers for multiple devices as described by the comments in
that file.

    cp wcscheduler.conf ~/.config/
    vim ~/.config/wcscheduler.conf

### Systemd Configuration for Auto Start etc

Copy the included
[`wcscheduler.service`](https://github.com/bulletmark/wcscheduler/blob/master/wcscheduler.service)
to `/etc/systemd/systemd/` and edit the `#TEMPLATE#` values within that
target file:

    sudo cp wcscheduler.service /etc/systemd/systemd/
    sudo vim /etc/systemd/systemd/wcscheduler.service

Then:

    sudo systemctl enable wcscheduler
    sudo systemctl start wcscheduler

If you change the configuration then restart with:

    sudo systemctl restart wcscheduler

To see status and logs:

    systemctl status wcscheduler
    journalctl -u wcscheduler

### IFTTT Webhook Configuration

You can set up an [IFTTT](https://ifttt.com/) webhook applet e.g. which
can be trigged by Google Assistant to switch your devices remotely by
voice command from your phone or from a Google home device. Configure a
[IFTTT](https://ifttt.com/) webhook POST JSON command with _webhook_ and
_action_ keys in the body as a minimum. You can also include the
_created_ key which can be used to time contrain the message (see the
comments about `webdelay` in
[`wcscheduler.conf`](https://github.com/bulletmark/wcscheduler/blob/master/wcscheduler.conf)).
The _webhook_ key must match the `webhook` name in the corresponding
`outputs` section of your `~/.config/wcscheduler.conf`. E.g.:

```
{
  "webhook": "<some_unique_text>"
  "action": "{{TextField}}",
  "created": "{{CreatedAt}}",
}
```

Be sure to specify `webport` in `~/.config/wcscheduler.conf` for the
port for the web server to listen on and receive JSON POST messages. If
`webport` is not set, or there are no `webhook` values set for any
`outputs`, then the internal web server will not be started. A typical
home user will need to forward the port from their internet router to
the Raspberry Pi running this application.

### Command Line Usage

```
usage: wcscheduler [-h] [-c CONFIG]

Program to schedule control of Watts Clever switches.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        alternative configuration file
```

<!-- vim: se ai syn=markdown: -->
