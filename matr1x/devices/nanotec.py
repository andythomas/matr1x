import time

from wrapt import synchronized

from .visadevice import VisaDevice


class NanotecPD4(VisaDevice):

    def __init__(self, interface, **kwargs):
        super().__init__(interface, write_termination="\r",
                         read_termination="\r", timeout=2, query_delay=0.02,
                         **kwargs)
        # read to kill first open error (reason unknown)
        time.sleep(0.2)
        try:
            self.readMoves()
        except Exception:
            pass

    def id(self):
        return self.query("v")

    # high level functions
    @synchronized
    def move(self, moves):
        # sets moves
        self.query("#1s" + str(int(moves)))
        # starts motor
        self.query("#1A")

    @synchronized
    def moveWait(self, moves):
        # moves
        self.move(moves)
        moving = True
        # and waits
        while moving is True:
            ret = self.query("#1$").strip("001$")
            moving = not bool(int(ret) & 0b1)

    def readMoves(self):
        pos = self.query("#1C")
        return pos.strip().replace('1C', '')

    def resetMoves(self):
        self.query("#1c")
