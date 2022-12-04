#!/usr/bin/python3
'Program to schedule or remote control Watts Clever switches'
# Mark Blakeney, May 2016.

# Standard packages
import sys
import platform
import time
import pickle
import threading
import urllib3
from datetime import datetime, date, timedelta
from pathlib import Path

# 3rd party packages
import requests
import wccontrol
import timesched

# Disable warning about SSL verification arising from requests library
urllib3.disable_warnings()

ON_STATES = {'on', 'enable', 'set', 'true', 'yes', '1'}
myhost = platform.node().lower()
sched = timesched.Scheduler()
lock = threading.Lock()
webdelay = 0
locations = {}
cachedir = None
cache_time_max = timedelta(days=30)

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

SUNAPI = 'https://api.sunrise-sunset.org/json?lat={}&lng={}&date={}&formatted=0'

# Daily time at which we fetch SUN times
SUNTIME = parsetime('00:01')

# Times we assume if web API request fails
SUNTIMES = {'sunrise': '06:00', 'sunset': '18:00'}

def fetchsun_api(coords, today):
    'Fetch sunrise/sunset data from web API'
    url = SUNAPI.format(coords[0], coords[1], today.isoformat())
    try:
        r = requests.get(url, verify=False)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f'Error: {str(e)}', file=sys.stderr)
        return None

    res = r.json()
    if not res or res.get('status') != 'OK':
        print(f'Status {res} error fetching {url}', file=sys.stderr)
        return None

    res = res.get('results')
    if not res:
        print(f'Results error fetching {url}', file=sys.stderr)
        return None

    return res

def fetchsun(coords, today):
    'Fetch sunrise/sunset data'
    coordstr = ','.join(str(c) for c in coords)
    cfile = Path(cachedir) / f'coords:{coordstr}'

    last_day = None
    if cache_time_max:
        try:
            with cfile.open('rb') as fp:
                last_day, last_res = pickle.load(fp)
        except Exception:
            pass
        else:
            # If we already have today cached then just use it now
            if last_day == today:
                print('Loaded cached sunset/rise times for today',
                        file=sys.stderr)
                return last_res

    res = fetchsun_api(coords, today)

    # If we failed to get times from the internet then use last values
    # from last cached fetch
    if res:
        with cfile.open('wb') as fp:
            pickle.dump((today, res), fp)
    elif last_day:
        if (today - last_day) > cache_time_max:
            cfile.unlink()
            print(f'Discarded cached sunset/rise times for {last_day}',
                    file=sys.stderr)
        else:
            print(f'Loaded cached sunset/rise times for {last_day}',
                    file=sys.stderr)
            res = last_res

    return res

def getsun(coords, event, today):
    'Cache all sunrise/sunset fetches for today'
    cached = False
    if getsun.day != today:
        getsun.cache.clear()
        getsun.day = today
    elif coords in getsun.cache:
        res = getsun.cache.get(coords)
        cached = True

    if not cached:
        res = fetchsun(coords, today)
        getsun.cache[coords] = res

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

            self.coords = tuple(float(v.strip()) for v in loc.split(','))

    def fetchtime(self):
        'Fetch event time'
        today = date.today()
        tevent = getsun(self.coords, self.event, today)
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
    if not hook:
        return 'webhook not defined'

    if not action:
        return 'action not defined'

    if created:
        ctime = datetime.strptime(created, '%B %d, %Y at %I:%M%p')
        ctimestr = ctime.isoformat(sep=' ', timespec='seconds')
        ctimestr = f' ({ctimestr})'
    else:
        ctimestr = ''

    print(f'Received webhook "{hook}" for "{action}"{ctimestr}')

    if created and webdelay and (datetime.now() - ctime) > webdelay:
        print(f'.. webhook "{hook}" too delayed (> "{webdelay}")')
        return 'Too delayed'

    job = Job.webhooks.get(hook)
    if not job:
        print(f'.. no job for webhook "{hook}"')
        return f'No job for {hook}'

    to_off = set(action.lower().split()).isdisjoint(ON_STATES)
    job.do(JobState(not to_off))
    return None

def init(prog, args, conf):
    'Set up each job, each with potentially multiple timers/hooks'
    global webdelay
    global cachedir
    global cache_time_max

    locations.update(conf.get('locations', {}))

    outputs = conf.get('outputs')
    if not outputs:
        print('No outputs configured')
        return 0, 0

    webdelay = conf.get('webdelay', 0)
    if webdelay:
        webdelay = timedelta(seconds=webdelay)

    cachedir = Path(f'~/.cache/{prog}/times').expanduser()
    cachedir.mkdir(parents=True, exist_ok=True)
    if args.no_cache:
        cache_time_max = None

    # Iterate over configured outputs
    now = datetime.now().time()
    for job in outputs:
        Job(job, now)

    return len(Job.jobs), len(Job.webhooks), sched.count()

def run():
    'Run all timers'
    sched.run()
