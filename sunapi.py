#!/usr/bin/python3
'Fetch sunrise/sunset times from web API'
# Mark Blakeney, May 2016.

import pickle
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 3rd party packages
import requests
import urllib3

# Disable warning about SSL verification arising from requests library
urllib3.disable_warnings()

_cachedir = None
_cache_time_max = timedelta(days=30)

SUNAPI = 'https://api.sunrise-sunset.org/json?lat={}&lng={}&date={}&formatted=0'

def _fetchsun_api(coords, today):
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

def _fetchsun(coords, today):
    'Fetch sunrise/sunset data, potentially from cache'
    coordstr = ','.join(str(c) for c in coords)
    cfile = Path(_cachedir) / f'coords:{coordstr}'

    last_day = None
    if _cache_time_max:
        try:
            with cfile.open('rb') as fp:
                last_day, last_res = pickle.load(fp)
        except Exception as e:
            print(f'pickle error loading {cfile}:', str(e), file=sys.stderr)
        else:
            # If we already have today cached then just use it now
            if last_day == today:
                print('Loaded cached sunset/rise times for today',
                        file=sys.stderr)
                return last_res

    res = _fetchsun_api(coords, today)

    # If we failed to get times from the internet then use last values
    # from last cached fetch
    if res:
        with cfile.open('wb') as fp:
            pickle.dump((today, res), fp)
    elif last_day:
        if (today - last_day) > _cache_time_max:
            cfile.unlink()
            print(f'Discarded cached sunset/rise times for {last_day}',
                    file=sys.stderr)
        else:
            print(f'Loaded cached sunset/rise times for {last_day}',
                    file=sys.stderr)
            res = last_res

    return res

def getsun(coords, event, today):
    'Fetch, cache, and return sunrise/sunset fetches for today'
    cached = False
    if getsun.day != today:
        getsun.cache.clear()
        getsun.day = today
    else:
        res = getsun.cache.get(coords)
        if res:
            cached = True

    if not cached:
        res = _fetchsun(coords, today)
        if res:
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

def init(prog, args):
    'Init this module'
    global _cachedir
    global _cache_time_max

    _cachedir = Path(f'~/.cache/{prog}/times').expanduser()
    _cachedir.mkdir(parents=True, exist_ok=True)
    if args.no_cache:
        _cache_time_max = None
