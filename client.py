import selectors
import socket
import traceback

from message import ClientMessage


class Client:

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sel = selectors.DefaultSelector()

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

    def start_connection (self):
        addr = (self._host, self._port)
        self._sock.setblocking(False)
        self._sock.connect_ex(addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        hello_server = "Hello Server"
        hello_request = {"content": hello_server, "encoding": "utf-8", "type" : "json/text"}
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
    host = "127.0.0.1"
    port = 12345
    client = Client(host, port)
    client.run()
