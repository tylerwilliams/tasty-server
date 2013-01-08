import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import logging
import optparse

import tornado
import tornado.options

from main import *

def setup_curses():
    try:
        import curses
    except ImportError:
        curses = False
    
    if curses and sys.stderr.isatty():
        try:
            curses.setupterm()
            if curses.tigetnum("colors") > 0:
                return True
        except Exception:
            pass
    return False

if __name__ == "__main__":
    usage = 'usage: %prog [options]\n' \
            'example:\n' \
            '\t %prog -f /path/to/tasty.conf'

    parser = optparse.OptionParser(usage=usage)

    parser.add_option("-f", "--config",
                      dest="config", default=None, type="str",
                      help="config file")

    parser.add_option("-s", "--host",
                    dest="host", default="0.0.0.0", type="str",
                    help="host interface")
                
    parser.add_option("-p", "--port",
                      dest="port", default=8888, type="int",
                      help="port number")
    
    color = setup_curses()
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(tornado.options._LogFormatter(color=color))
    
    logging.getLogger().addHandler(sh)
    logging.getLogger().setLevel(logging.DEBUG)
    
    (options, args) = parser.parse_args()
    settings_manager = settings.SettingsManager(options.config)
    application = get_app(settings_manager)
    application.listen(options.port)
    print "using config: %s" % options.config
    print "http://%s:%d/" % (options.host, options.port)
    tornado.ioloop.IOLoop.instance().start()


