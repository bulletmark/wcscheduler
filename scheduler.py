#!/usr/bin/python3
'Program to schedule or remote control Watts Clever switches'
# Mark Blakeney, May 2016.

# Standard packages
import sys
import platform
import time
import threading
from datetime import datetime, date, timedelta

# 3rd party packages
import requests
import wccontrol
import timesched

ON_STATES = {'1', 'on', 'true', 'yes', 'set'}
myhost = platform.node().lower()
sched = timesched.Scheduler()
lock = threading.Lock()
webdelay = 0
webdelay = 0
locations = {}

def parsetime(timestr):
    'Parse time value from given string'
    length = len(timestr)
    if length == 5:
        tm = datetime.strptime(timestr, '%H:%M').time()
    elif length == 8:
        tm = datetime.strptime(timestr, '%H:%M:%S').time()
    else:
        sys.exit(f'Error: Invalid configured time string "{timestr}".')

    return tm

SUNAPI = 'https://api.sunrise-sunset.org/json?lat={}&lng={}&formatted=0'

# Daily time at which we fetch SUN times
SUNTIME = parsetime('00:01')

# Times we assume if web API request fails
SUNTIMES = {'sunrise': '06:00', 'sunset': '18:00'}

def fetchsun(url):
    'Fetch sunrise/sunset data from web API'
    r = requests.get(url)
    if r.status_code != requests.codes.ok:
        print(f'Error {r.status_code} fetching {url}',
                file=sys.stderr)
        return None
    res = r.json()
    if not res or res.get('status') != 'OK':
        print(f'Status error fetching {url}', file=sys.stderr)
        return None
    res = res.get('results')
    if not res:
        print(f'Results error fetching {url}', file=sys.stderr)
        return None

    return res

def getsun(url, event, today):
    'Cache all sunrise/sunset fetches for today'
    fullurl = f'{url}&date={today.isoformat()}'

    cached = False
    if getsun.day != today:
        getsun.cache.clear()
        getsun.day = today
    elif fullurl in getsun.cache:
        res = getsun.cache.get(fullurl)
        cached = True

    if not cached:
        res = fetchsun(fullurl)
        getsun.cache[fullurl] = res

    if not res:
        return None

    res = res.get(event)
    if not res:
        print(f'Results error, no {event} value', file=sys.stderr)
        return None

    # Convert trailing timezone +HH:MM to +HHMM for %z parse
    if res[22] == ':':
        res = res[:22] + res[23:]

    # Return as local time
    return datetime.strptime(res, "%Y-%m-%dT%H:%M:%S%z").astimezone()

getsun.day = None
getsun.cache = {}

class JobState:
    'Wrapper for callback state'
    def __init__(self, state, event=None, text=None):
        self.state = state
        self.event = event
        self.statetext = 'on' if state else 'off'

        if text:
            for c in ('+', '-'):
                signx = text.find(c)
                if signx >= 0:
                    break

            if signx >= 0:
                self.timex = datetime.combine(date.min,
                        parsetime(text[(signx + 1):])) - datetime.min
                self.eventdesc = f'{event} {c} {self.timex}'
                if c == '-':
                    self.timex = -self.timex

                text = text[:signx]
            else:
                self.timex = timedelta()

            loc = locations.get(text)
            if not loc:
                sys.exit(f'Error: Location "{text}" not defined.')

            lat, lng = (float(v.strip()) for v in loc.split(','))
            self.url = SUNAPI.format(lat, lng)

    def fetchtime(self):
        'Fetch event time'
        today = date.today()
        tevent = getsun(self.url, self.event, today)
        if not tevent:
            tevent = datetime.combine(today,
                    parsetime(SUNTIMES.get(self.event)))

        return (tevent + self.timex).time()

class Job:
    'Class to manage each timer/webhook job'
    webhooks = {}
    jobs = []

    def __init__(self, conf, now):
        'Constructor'
        host = conf.get('host')
        # Ignore this job if configured for specific other host
        if host and host.lower() != myhost:
            return

        # Allow single or multiple addresses
        address = conf.get('address', 6)
        self.addresses = [int(a.strip()) for a in address.split(',')] \
                if ',' in str(address) else [int(address)]

        # Allow single or multiple groups
        group = conf.get('group', 0)
        self.groups = [int(g.strip()) for g in group.split(',')] \
                if ',' in str(group) else [int(group)]

        self.lastpair = (self.groups[-1], self.addresses[-1])
        self.name = conf.get('name', f'Address {address}')
        self.gpiopin = conf.get('gpiopin')

        # Set up webhook, if configured
        webhook = conf.get('webhook')
        if webhook:
            if webhook in self.webhooks:
                sys.exit(f'Error: Web hook "{webhook}" already configured.')
            self.webhooks[webhook] = self

        times = conf.get('times')
        if not times:
            if not webhook:
                sys.exit('Error: must define either timer or webhook '
                        f'for {self.name}.')
            return

        # Iterate over each configured off/on times, if configured ..
        days = conf.get('days', timesched.DAYS_STRING)
        on_today = date.today().weekday() in timesched.parse_days(days)

        # Allow text or int for initial state
        state = conf.get('start')
        if type(state) is str:
            state = state.lower() in ON_STATES

        istate = state = bool(state)

        for t in times.split(','):
            state = not state
            field = t.strip()
            firsttime = None
            for event in SUNTIMES:
                if field.lower().startswith(f'{event}@'):
                    jobtime = SUNTIME
                    jobstate = JobState(state, event, field[(len(event) + 1):])
                    desc = jobstate.eventdesc

                    # Ensure first activation for today
                    if on_today:
                        firsttime = jobstate.fetchtime()
                        desc += f' (1st {firsttime})'
                        if firsttime > now:
                            sched.oneshot(firsttime, 0, self.do,
                                    JobState(state))
                    break
            else:
                jobtime = parsetime(field)
                jobstate = JobState(state)
                desc = str(jobtime)
                if on_today:
                    firsttime = jobtime

            sched.repeat_on_days(days, jobtime, 0, self.do, jobstate)
            print(f'{self.name} set {jobstate.statetext} at {days} {desc}')

            # Record starting state
            if firsttime and firsttime <= now:
                istate = state

        # Ensure starting state is set at startup
        self.do(JobState(istate))
        self.jobs.append(self)

    def do(self, jobstate):
        'Called each each timer expiry to do output'
        if jobstate.event:
            sched.oneshot(jobstate.fetchtime(), 0, self.do,
                    JobState(jobstate.state))
        else:
            with lock:
                print(f'Set {self.name} {jobstate.statetext}')
                for group in self.groups:
                    for addr in self.addresses:
                        wccontrol.set(group, addr, jobstate.state, self.gpiopin)
                        if (group, addr) != self.lastpair:
                            time.sleep(0.2)

def webhook(hook, action, created=None):
    'Called on receipt of external webhook'
    print(f'Received webhook "{hook}" to "{action}"')
    if created and webdelay:
        now = datetime.now()
        ctime = datetime.strptime(created, '%B %d, %Y at %I:%M%p')
        if (now - ctime) > webdelay:
            c = ctime.isoformat(' ', 'minutes')
            print(f'Webhook too delayed: {c}')
            return

    job = Job.webhooks.get(hook)
    if job:
        job.do(JobState(action.lower() in ON_STATES))
    else:
        print(f'No job for webhook "{webhook}"')

def init(args, conf):
    'Set up each job, each with potentially multiple timers/hooks'
    global webdelay

    locations.update(conf.get('locations', {}))

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

    return len(Job.jobs), len(Job.webhooks), sched.count()

def run():
    'Run all timers'
    sched.run()
