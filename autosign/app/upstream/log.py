"""Legacy logs may contain upstream responses or credentials; never emit them."""
class Log:
    def info(self, *args):
        pass
    debug = error = warning = critical = info
