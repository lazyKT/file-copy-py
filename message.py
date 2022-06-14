"""
: Application Message Class
: Message consists of 3 parts
:   1) `Message Header`
:       - 2-byte Integer
:       - Network-byteorder (Big Indian)
:       - Indicates length of JSON Config Header
:   2) `Json Config Header`
:       - Specify configuration of Message Content (type, content-lenght, content etc.)
:       - Encoding: utf-8 (by default)
:       - Length: specified by `Message Header`
:   3)  `Variable-length Message Content`
:       - Type: Specified in JSON Config Header
:       - Encoding: Specified in JSON Config Header
:       - Length: specified in JSON Header
"""

import io
import struct
import sys
import json
import selectors
from socket import socket
from datetime import datetime
import traceback


timestamp_fmt = "%Y-%m-%d %H:%M:%S"
MSG_LEN = 4096


class BaseMessage:

    def __init__ (self, selector:selectors, sock:socket, addr:str):
        self._sel = selector
        self._sock = sock
        self._addr = addr
        self._recv_bytes = b""
        self._sent_bytes = b""
        self._json_header_len = None
        self._json_header = None
        self._response = None
        self._request = None
        self._is_response_created = False

    def _decode_json (self, content_bytes:json, encoding="utf-8"):
        io_wrapper = io.TextIOWrapper(
            io.BytesIO(content_bytes), encoding=encoding, newline=""
        )
        content = json.load(io_wrapper)
        io_wrapper.close()
        return content

    def _encode_json (self, content:dict, encoding:str="utf-8"):
        return json.dumps(content, ensure_ascii=False).encode(encoding=encoding)

    def _process_message_header (self):
        header_len = 2 # 2 bytes
        if len (self._recv_bytes) > header_len:
            self._json_header_len = struct.unpack(
                ">H", self._recv_bytes[:header_len]
            )[0]
            self._recv_bytes = self._recv_bytes[header_len:]

    def _process_json_header (self):
        header_len = self._json_header_len
        if len(self._recv_bytes) >= header_len:
            self._json_header = self._decode_json(
                self._recv_bytes[:header_len],
                encoding="utf-8"
            )
            for cfg in ("byteorder", "content-length", "content-type", "content-encoding"):
                if cfg not in self._json_header:
                    raise ValueError(f"Missing JSON Header : {cfg}")
                    # !!! TO DO: send the error message to another peer
            self._recv_bytes = self._recv_bytes[header_len:]

    def _process_request (self):
        if self._request is None:
            #: create one if no existing request
            content_len = self._json_header["content-length"]
            if len(self._recv_bytes) < content_len:
                return
            data = self._recv_bytes[:content_len]
            self._recv_bytes = self._recv_bytes[content_len:]
            encoding = self._json_header["content-encoding"]
            self._request = self._decode_json(data, encoding)
            current_ts = datetime.strftime(datetime.now(), timestamp_fmt)
            print (f"[{current_ts}] Received Request {self._request!r} from {self._addr}")
            self._set_selector_events_mask("w")

    def _set_selector_events_mask(self, mode:str):
        """Set selector to monitor to given event"""
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError (f"Invalud events mask mode {mode!r}")
            # !!! TO DO: send the error message to another peer
        self._sel.modify(self._sock, events, data=self)

    def _create_json_response (self, content:dict=None):
        if content is None:
            content = {"result" : "This is test Message Response Content"}
        content_encoding = "utf-8"
        response = {
            "content_bytes" : self._encode_json(content, content_encoding),
            "content_type" : "text/json",
            "content_encoding" : content_encoding
        }
        return response

    def _create_response (self):
        """Create Response Object to write back to the Socket"""
        response = self._create_json_response()
        message = self._create_message(**response)
        self._is_response_created = True
        self._sent_bytes += message


    def _create_message (self, *, content_bytes, content_type, content_encoding):
        json_header = {
            "byteorder" : sys.byteorder,
            "content-type" : content_type,
            "content-encoding" : content_encoding,
            "content-length" : len(content_bytes)
        }
        json_header_bytes = self._encode_json (json_header, content_encoding)
        message_header = struct.pack(">H", len(json_header_bytes))
        message = message_header + json_header_bytes + content_bytes
        return message

    def _read (self):
        """Read Raw Bytes from Socket"""
        try:
            data = self._sock.recv(MSG_LEN)
        except BlockingIOError:
            pass
        else:
            if data:
                self._recv_bytes += data
            else:
                raise RuntimeError("Peer closed.")

    def _write (self):
        """Write sent buffer to Socket"""
        if self._sent_bytes:
            current_ts = datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')
            print (f"[{current_ts}] Sending {self._sent_bytes!r} to {self._addr}")
            try:
                sent = self._sock.send(self._sent_bytes)
            except BlockingIOError as bie: 
                print (f"[BLOCKING IO ERROR] {repr(bie)}")
            else:
                self._sent_bytes = self._sent_bytes[sent:]
                print ('sent :', sent)

    def read (self):
        """Will be overwritten by children classes"""
        pass

    def write (self):
        """Will be overwritten by children classes"""
        pass

    def process_events (self, mask):
        """Based on the mask event, Read or write from/to the socket"""
        if mask & selectors.EVENT_READ:
            self.read()
        if mask & selectors.EVENT_WRITE:
            self.write()

    def close (self):
        try:
            print ("Closing Message Object!")
            self._sel.unregister(self._sock)
            self._sock.shutdown(1)
            self._sock.close()
        except OSError as oe:
            print (f"[OS ERROR] {repr(oe)}")
        except Exception:
            print ("Uncaught error", traceback.format_exc())
        finally:
            self.sock = None


class ServerMessage (BaseMessage):

    def __init__ (self, selector:selectors, sock: socket, addr:str):
        super().__init__(selector, sock, addr)

    def write(self):
        if self._request and not self._is_response_created:
                self._create_response()
        if self._sent_bytes:
            current_ts = datetime.strftime(datetime.now(), timestamp_fmt)
            print (f"[{current_ts}] Sending {self._sent_bytes!r} to {self._addr}")
            try:
                sent = self._sock.send(self._sent_bytes)
            except BlockingIOError:
                pass   
            else:
                self._sent_bytes = self._sent_bytes[sent:]
                if sent and not self._sent_bytes:
                    self.close()

    def write_err_response (self, err_message:str):
        content = {"result" : f"[Error] {err_message}"}
        response = self._create_json_response(content)
        message = self._create_message(**response)
        self._sent_bytes += message
        current_ts = datetime.strftime(datetime.now(), timestamp_fmt)
        print (f"[{current_ts}] Sending {self._sent_bytes!r} to {self._addr}")
        try:
            sent = self._sock.send(self._sent_bytes)
        except BlockingIOError:
            pass   
        else:
            self._sent_bytes = self._sent_bytes[sent:]
            if sent and not self._sent_bytes:
                self.close()

    def read (self):
        #: read the raw content
        self._read()
        #: Read Recieved Raw Bytes to get Json Header Length
        if self._json_header_len is None:
            self._process_message_header()
        #: Read Json Header to get Message Content Length
        if self._json_header is None:
            self._process_json_header()
        if self._request is None:
            self._process_request()

class ClientMessage (BaseMessage):

    def __init__ (self, selector:selectors, sock:socket, addr:str, request:dict):
        super().__init__(selector, sock, addr)
        self._request_queued = False
        self._request = request

    def _queue_request (self):
        """Create request object and write to sent buffer"""
        content = self._request["content"]
        content_type = self._request["type"]
        content_encoding = self._request["encoding"]
        req = {
            "content_bytes" : self._encode_json(content, content_encoding),
            "content_type" : content_type,
            "content_encoding" : content_encoding
        }
        message = self._create_message(**req)
        self._sent_bytes += message
        self._request_queued = True

    def write (self):
        #: queue the request, if it hasn't been queued
        if not self._request_queued:
            self._queue_request()
        self._write()
        if self._request_queued and not self._sent_bytes:
                #: if there no buffer left to sent, listen for the read events
                self._set_selector_events_mask("r")

    def read (self):
        self._read()
        if self._json_header_len is None:
            self._process_message_header()
        if self._json_header is None:
            self._process_json_header()
        if self._response is None:
            self._process_response()

    def _process_response (self):
        content_len = self._json_header["content-length"]
        if len(self._recv_bytes) < content_len:
            return
        data = self._recv_bytes[:content_len]
        self._recv_bytes = self._recv_bytes[content_len:]
        if self._json_header["content-type"] == "text/json":
            encoding = self._json_header["content-encoding"]
            self._response = self._decode_json (data, encoding)
        current_ts = datetime.strftime(datetime.now(), timestamp_fmt)
        print (f"[{current_ts}] Received response {self._response!r} from {self._addr}")
        self.close()

