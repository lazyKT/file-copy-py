import sys
import selectors
import socket
import traceback

from message import ClientMessage


class Client:

    def __init__(self, host, port, data:bytes):
        self._host = host
        self._port = port
        self._sel = selectors.DefaultSelector()
        self._sock = None
        self._data = data

    @property
    def host (self):
        """Client Host Property"""
        return self._host

    @property
    def port (self):
        """Client Port Property"""
        return self._port

    @property
    def socket (self):
        """Client Socket Property"""
        return self._sock

    @property
    def selector (self):
        """Client Selector Property"""
        return self._sel

    @property
    def data (self):
        """File content in Bytes which will be sent by Client"""
        return self._data

    def start_connection (self):
        addr = (self._host, self._port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setblocking(False)
        self._sock.connect_ex(addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        hello_request = {"content": self._data, "encoding": "utf-8", "type" : "bytes"}
        message = ClientMessage(self._sel, self._sock, self._host, hello_request)
        self._sel.register(self._sock, events, data=message)

    def run (self):
        """Start Client Socket"""
        self.start_connection()
        try:
            while True:
                events = self._sel.select(timeout=1)
                for key, mask in events:
                    message = key.data
                    try:
                        message.process_events(mask)
                    except Exception:
                        print ("Uncaught error", traceback.format_exc())
                        message.close()
                if not self._sel.get_map():
                    break
        except KeyboardInterrupt:
            print ("Caught keyboard interrupt, exiting ...")
        finally:
            self._sel.close()
            self._sock.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[Usage] python client.py <file>")
        sys.exit(1)

    filename = sys.argv[1]
    data = None
    with open(filename, 'rb') as f:
        data = f.read()

    host = "127.0.0.1"
    port = 12345
    client = Client(host, port, data)
    client.run()
