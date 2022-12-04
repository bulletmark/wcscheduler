#!/usr/bin/python3
'Program to set PI switch controls or off'
# Mark Blakeney, Nov 2019.
import scheduler

_port = None

def init(prog, args, conf):
    'Set up web app'
    global _port

    _port = conf.get('webport')
    if not _port:
        print('Webhook port not configured')
        return False

    return True

def run():
    'Run web app'
    from bottle import Bottle, request, HTTPResponse

    app = Bottle()

    @app.post('/webhook')
    def api():
        'Process an incoming message'
        if request.json:
            error = scheduler.webhook(request.json.get('webhook'),
                                    request.json.get('action'),
                                    request.json.get('created'))
        else:
            error = 'No json data'

        if error:
            return HTTPResponse({'Error': error}, 400)

        return {'Result': 'Success'}

    # Will block here, essentially forever
    app.run(host='0.0.0.0', port=int(_port), server='bjoern')
