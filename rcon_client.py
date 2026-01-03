#!/usr/bin/env python3
"""Minimal Minecraft RCON client (Valve RCON protocol) to send a single command and print response."""
import argparse
import socket
import struct

TYPE_AUTH = 3
TYPE_COMMAND = 2

class RconError(Exception):
    pass

class Rcon:
    def __init__(self, host, port, password, timeout=5.0):
        self.host = host
        self.port = port
        self.password = password
        self.socket = socket.create_connection((host, port), timeout)
        self.socket.settimeout(timeout)
        self._request_id = 0

    def _pack(self, req_id, typ, payload):
        data = struct.pack('<ii', req_id, typ) + payload.encode('utf8') + b'\x00\x00'
        return struct.pack('<i', len(data)) + data

    def _recv(self):
        data = self.socket.recv(4)
        if len(data) < 4:
            raise RconError('connection closed or timeout while reading length')
        (length,) = struct.unpack('<i', data)
        body = b''
        while len(body) < length:
            chunk = self.socket.recv(length - len(body))
            if not chunk:
                raise RconError('connection closed while reading body')
            body += chunk
        req_id, typ = struct.unpack('<ii', body[:8])
        payload = body[8:-2].decode('utf8', errors='replace')
        return req_id, typ, payload

    def auth(self):
        self._request_id += 1
        req_id = self._request_id
        self.socket.sendall(self._pack(req_id, TYPE_AUTH, self.password))
        res_id, typ, payload = self._recv()
        if res_id == -1:
            raise RconError('Authentication failed')
        return payload

    def command(self, cmd):
        self._request_id += 1
        req_id = self._request_id
        self.socket.sendall(self._pack(req_id, TYPE_COMMAND, cmd))
        # Some servers may reply with two split packets; read until we get a packet with our req_id
        res_parts = []
        while True:
            res_id, typ, payload = self._recv()
            if res_id != req_id and res_id != 0:
                # ignore unrelated
                continue
            res_parts.append(payload)
            # If payload length less than 4096, likely last packet
            if len(payload) < 4096:
                break
        return ''.join(res_parts)

    def close(self):
        try:
            self.socket.close()
        except Exception:
            pass

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=25575)
    p.add_argument('--password', required=True)
    p.add_argument('--cmd', required=True)
    args = p.parse_args()

    c = Rcon(args.host, args.port, args.password)
    try:
        c.auth()
    except Exception as e:
        print('Auth failed:', e)
        raise
    out = c.command(args.cmd)
    print(out)
    c.close()
