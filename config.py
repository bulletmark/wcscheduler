#!env/bin/python -u
'Module to search for and read config file.'
# Requires python 3.5+
# Mark Blakeney, May 2016.

# Standard packages
import os, sys
from pathlib import Path

# 3rd party imports
import ruamel.yaml as yaml

def get(conffile, altfile=None, user=''):
    'Return a configuration dict'
    # Search for configuration file. Use explicit file else look for
    # file in search dir order.
    if altfile:
        cfile = Path(altfile)
        if not cfile.exists():
            print('Config file "{}" does not exist.'.format(cfile),
                    file=sys.stderr)
            return None
    else:
        userdir = Path(os.getenv('XDG_CONFIG_HOME',
            '{}/.config'.format(f'~{user}'))).expanduser()
        confdirs = (userdir, Path('.'))

        for confdir in confdirs:
            cfile = confdir / conffile
            if cfile.exists():
                break
        else:
            print('No {} file found.'.format(conffile), file=sys.stderr)
            return None

    # Read config file
    with cfile.open() as fp:
        conf = yaml.safe_load(fp)

    return conf

if __name__ == '__main__':
    import pprint
    pprint.pprint(get(Path.cwd().name + '.conf'))
