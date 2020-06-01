#!/usr/bin/python3
'Program to schedule or remote control Watts Clever switches'
# Requires python 3.5+
# Mark Blakeney, May 2016.

# Standard packages
import sys
import platform
import time
import threading
from datetime import datetime, timedelta

# 3rd party packages
import wccontrol
import timesched

ON_STATES = set(('1', 'on', 'true', 'yes', 'set'))
myhost = platform.node().lower()
sched = timesched.Scheduler()
lock = threading.Lock()
webdelay = 0

def parsetime(timestr):
    'Parse time value from given string'
    length = len(timestr)

    if length == 5:
        tm = datetime.strptime(timestr, '%H:%M').time()
    elif length == 8:
        tm = datetime.strptime(timestr, '%H:%M:%S').time()
    else:
        sys.exit('Invalid configured time string "{}"'.format(timestr))

    return tm

def text(state):
    'Convert state to loggable text'
    return 'on' if state else 'off'

class Job:
    'Class to manage each timer/webhook job'
    webhooks = {}
    timers = []

    def __init__(self, conf, now):
        'Constructor'
        host = conf.get('host')
        # Ignore this job if configured for specific other host
        if host and host.lower() != myhost:
            return

        # Allow single or multiple addresses
        address = conf.get('address', 6)
        self.addresses = [int(a) for a in address.split(',')] \
                if ',' in str(address) else [int(address)]

        # Allow single or multiple groups
        group = conf.get('group', 0)
        self.groups = [int(g) for g in group.split(',')] \
                if ',' in str(group) else [int(group)]

        self.lastpair = (self.groups[-1], self.addresses[-1])
        self.name = conf.get('name', 'Address {}'.format(address))
        self.gpiopin = conf.get('gpiopin')

        # Set up webhook, if configured
        webhook = conf.get('webhook')
        if webhook:
            if webhook in self.webhooks:
                print('Web hook {} already configured'.format(webhook),
                        file=sys.stderr)
            else:
                self.webhooks[webhook] = self

        times = conf.get('times')
        if not times:
            return

        # Allow text or int for initial state
        state = conf.get('start')
        if type(state) is str:
            state = state.lower() in ON_STATES

        istate = bool(state)
        inited = False
        state = not istate

        # Iterate over each configured off/on times, if configured ..
        days = conf.get('days', timesched.DAYS_STRING)
        for p, t in enumerate(times.split(',')):
            jobtime = parsetime(t.strip())
            sched.repeat_on_days(days, jobtime, p, self.do, state)
            print('{} set {} at {} {}'.format(self.name, text(state),
                days, jobtime))
            state = not state

            if not inited and jobtime >= now:
                istate = state
                inited = True

        # Ensure assumed starting state is set at startup
        self.do(istate)
        self.timers.append(self)

    def do(self, state):
        'Called each each timer expiry to do output'
        with lock:
            print('Set {} {}'.format(self.name, text(state)))
            for group in self.groups:
                for addr in self.addresses:
                    wccontrol.set(group, addr, state, self.gpiopin)
                    if (group, addr) != self.lastpair:
                        time.sleep(0.2)

def webhook(hook, action, created=None):
    'Called on receipt of external webhook'
    print('Received webhook "{}" to "{}"'.format(hook, action))
    if created and webdelay:
        now = datetime.now()
        ctime = datetime.strptime(created, '%B %d, %Y at %I:%M%p')
        if (now - ctime) > webdelay:
            print('Webhook too delayed: {}'.format(
                ctime.isoformat(' ', 'minutes')))
            return

    job = Job.webhooks.get(hook)
    if job:
        job.do(action.lower() in ON_STATES)
    else:
        print('No job for webhook "{}"'.format(webhook))

def init(args, conf):
    'Set up each job, each with potentially multiple timers/hooks'
    global webdelay

    outputs = conf.get('outputs')
    if not outputs:
        print('No outputs configured')
        return 0, 0

    webdelay = conf.get('webdelay', 0)
    if webdelay:
        webdelay = timedelta(seconds=webdelay)

    # Iterate over configured outputs
    now = datetime.now().time()
    for job in outputs:
        Job(job, now)

    return len(Job.timers), len(Job.webhooks)

def run():
    'Run all timers'
    sched.run()
