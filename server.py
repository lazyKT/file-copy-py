#: server

import traceback
import sys
import socket
import selectors
import types

from message import ServerMessage
from exceptions import MissingConfigHeaderError


class Server:

    def __init__(self, host:str, port:int):
        self._sel = selectors.DefaultSelector()
        self._lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._lsock.bind((host, port))
        self._host = host

    @property
    def sel (self):
        """Server Selector Property"""
        return self._sel
    
    @property
    def sock (self) -> socket.socket:
        """Server Socket Property"""
        return self._lsock

    @property
    def host (self) -> str:
        """Server Host Address Property"""
        return self._host

    def _register (self, sock:socket.socket):
        conn, addr = sock.accept()
        print (f"Accepted connection from {addr}")
        conn.setblocking(False)
        message = ServerMessage(self._sel, conn, self._host)
        self._sel.register(conn, selectors.EVENT_READ, data=message)

    def _listen (self):
        self._lsock.listen()
        self._lsock.setblocking(False)
        print ("Listening ...")
        self._sel.register(self._lsock, selectors.EVENT_READ, data=None)

    def run (self):
        self._listen()
        try:
            while True:
                events = self._sel.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        #: new client socket registration
                        self._register(key.fileobj)
                    else:
                        #: read data sent from client socket
                        message = key.data
                        try:
                            message.process_events(mask)
                        except MissingConfigHeaderError as mche:
                            print ("[Error]", repr(mche))
                            #: Inform Client about the error message
                            message.write_err_response(repr(mche))
                            message.close()
                        except Exception:
                            print ("Uncaught exception at Server.run() %s" % traceback.format_exc())
                            message.close()
                            break
        except KeyboardInterrupt:
            print("Caught keyboard interrupt")
        finally:
            self._lsock.close()
            self._sel.close()


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 12345
    server = Server(host, port)
    server.run()