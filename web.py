#!/usr/bin/python3
'Program to set PI switch controls or off'
# Mark Blakeney, Nov 2019.
import scheduler

_port = None

def init(args, conf):
    'Set up web app'
    global _port

    _port = conf.get('webport')
    if not _port:
        print('Webhook port not configured')
        return False

    return True

def run():
    'Run web app'
    import meinheld
    from bottle import Bottle, request

    app = Bottle()

    @app.post('/api')
    def api():
        'Process an incoming message'
        scheduler.webhook(request.json['webhook'], request.json['action'],
                request.json.get('created'))
        return 'ok'

    # Disable access logging to improve performance. We are doing our
    # own logging.
    meinheld.set_access_logger(None)

    # Will block here, essentially forever
    app.run(host='0.0.0.0', port=int(_port), server='meinheld')
