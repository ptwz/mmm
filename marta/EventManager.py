from multiprocessing import Process, Queue
from multiprocessing.managers import BaseManager

class QueueManager(BaseManager):
    queues = {}

    @classmethod
    def make_queue(cls, queue_name):
        if queue_name in cls.queues:
            return

        q = Queue()
        cls.queues[queue_name] = q

    @classmethod
    def manager(cls, server=False):
        mgr = cls(address=('', 50000), authkey=b'abracadabra')
        print(cls.queues)

        if server:
            for queue_name in cls.queues:
                cls.register('get_'+queue_name, callable=lambda: cls.queues[queue_name])
            s = mgr.get_server()
            return s.serve_forever()

        for queue_name in cls.queues:
            cls.register('get_'+queue_name)
            #cls.queues[queue_name] = cls.get_
        mgr.connect()
        return mgr

class Server(Process):
    def __init__(self):
        super(Process, self).__init__()

    def run(self):
        QueueManager.manager(server=True)
