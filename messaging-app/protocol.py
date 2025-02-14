import struct
import json

class Message:
    """ Represents a generic message with a type and data payload. """
    def __init__(self, msg_type, data):
        self.msg_type = msg_type
        self.data = data

    def __repr__(self):
        return f"<Message type={self.msg_type}, data={self.data}>"

class JSONProtocolHandler:
    """ Handles sending and receiving JSON-based messages with length-prefixing. """
    def send(self, conn, message: Message):
        payload = {
            "msg_type": message.msg_type,
            "data": message.data
        }
        encoded = json.dumps(payload).encode("utf-8")
        conn.sendall(struct.pack("!I", len(encoded)))
        conn.sendall(encoded)

    def receive(self, conn):
        length_prefix = conn.recv(4)
        if not length_prefix:
            return None
        (length,) = struct.unpack("!I", length_prefix)
        if length == 0:
            return None
        data = conn.recv(length)
        if not data:
            return None
        payload = json.loads(data.decode("utf-8"))
        return Message(payload["msg_type"], payload["data"])

import struct
from protocol import Message  # or wherever your Message class is defined

class CustomProtocolHandler:
    """
    Converts between your internal Message(msg_type, data=dict)
    and a minimal binary format:
    
      [op_id: 1 byte] + [fields...]
    
    Each operation's fields are encoded/decoded per your specification.
    """

    def __init__(self):
        # Map operation code -> msg_type
        self.command_to_msgtype = {
            1:  "signup",              # example if you choose
            2:  "login",
            3:  "logout",
            4:  "count_unread",
            5:  "send_message",
            6:  "send_messages_to_client",
            7:  "fetch_away_msgs",
            8:  "list_accounts",
            9:  "delete_messages",
            10: "delete_account",
            11: "reset_db",
            12: "response",
            255:"failure"
        }
        # Inverse map: msg_type -> operation code
        self.msgtype_to_command = {v:k for k,v in self.command_to_msgtype.items()}

    ############################################################
    # Public methods: send() and receive()
    ############################################################

    def send(self, conn, message: Message):
        """
        Encode a high-level `message` into the custom binary wire format
        and send it over 'conn'.
        
        Example usage from client:
          msg = Message("send_message", {
              "sender": "Alice",
              "recipient": "Bob",
              "content": "Hello, Bob!"
          })
          self.send(sock, msg)
        """
        op_id = self.msgtype_to_command.get(message.msg_type, 255) # default to error
        data = message.data or {}

        # Build the binary packet
        packet = self._encode_packet(op_id, message.msg_type, data)
        print(packet)

        # Send the result
        conn.sendall(packet)

    def receive(self, conn):
        """
        Read from 'conn' and decode a single message in the custom binary
        wire format, returning a Message(msg_type, data=...).
        If nothing is available (e.g. closed socket), return None.
        """
        # First, read 1 byte for the operation ID
        op_id_raw = self._recv_exact(conn, 1)
        if not op_id_raw:
            return None  # means connection closed or no data

        op_id = op_id_raw[0]  # single byte

        # Based on the op_id, parse the rest
        msg_type = self.command_to_msgtype.get(op_id, "unknown_command")

        # We'll parse the body according to the recognized operation
        data = self._decode_packet(conn, op_id, msg_type)
        if data is None:
            # In case of partial data or error, return None
            return None

        # Return a standard Message object
        return Message(msg_type, data)

    ############################################################
    # Internal helper: _encode_packet
    ############################################################

    def _encode_packet(self, op_id, msg_type, data):
        """
        Given an op_id and data, build the minimal binary format
        matching your protocol spec for that operation.
        """
        # Start with the 1-byte op_id
        packet = struct.pack("!B", op_id)

        if msg_type == "signup":
            # Operation ID = 1
            # [op_id:1] [username_length:1] [username] [password_length:1] [password]
            username = data.get("username", "")
            password = data.get("password", "")
            user_bytes = username.encode("utf-8")
            pass_bytes = password.encode("utf-8")

            packet += struct.pack("!B", len(user_bytes))
            packet += user_bytes
            packet += struct.pack("!B", len(pass_bytes))
            packet += pass_bytes

        elif msg_type == "login":
            # Operation ID = 2
            # [op_id:1] [username_length:1] [username] [password_length:1] [password]
            username = data.get("username", "")
            pw_hash  = data.get("password", "")
            unread_count = data.get("unread_count", "")

            user_bytes = username.encode("utf-8")
            pw_bytes   = pw_hash.encode("utf-8")
            unread_count_bytes = unread_count.encode("utf-8")

            packet += struct.pack("!B", len(user_bytes))
            packet += user_bytes
            packet += struct.pack("!B", len(pw_bytes))
            packet += pw_bytes
            packet += struct.pack("!H", len(unread_count_bytes))
            packet += unread_count_bytes

        elif msg_type == "logout":
            # Operation ID = 3
            # [op_id:1] -> no extra fields
            pass

        elif msg_type == "count_unread":
            # Operation ID = 4
            # [op_id:1] -> no extra fields
            pass

        elif msg_type == "send_message":
            # [op_id=5]
            # [sender_len:1][sender]
            # [recipient_len:1][recipient]
            # [msg_len:2][message]
            
            sender = data.get("sender", "")
            recipient = data.get("recipient", "")
            content   = data.get("content", "")
            
            s_bytes = sender.encode("utf-8")
            r_bytes = recipient.encode("utf-8")
            c_bytes = content.encode("utf-8")
            
            packet += struct.pack("!B", len(s_bytes))
            packet += s_bytes
            packet += struct.pack("!B", len(r_bytes))
            packet += r_bytes
            packet += struct.pack("!H", len(c_bytes))
            packet += c_bytes

        elif msg_type == "send_messages_to_client":
            # Operation ID = 6
            # [op_id:1] -> no extra fields
            pass

        elif msg_type == "fetch_away_msgs":
            # Operation ID = 7
            # [op_id:1] [limit:1]
            limit = data.get("limit", 10)
            if limit > 255:
                limit = 255
            packet += struct.pack("!B", limit)

        elif msg_type == "list_accounts":
            # Operation ID = 8
            # [op_id:1] [count:1] [start:4] [pattern_len:1] [pattern_bytes]
            pattern = data.get("pattern", "")
            start   = data.get("start", 0)   # 4-byte offset
            count   = data.get("count", 10)  # 1-byte limit

            if count > 255:
                count = 255
            packet += struct.pack("!B", count)      # 1 byte
            packet += struct.pack("!I", start)      # 4 bytes, big-endian

            pattern_bytes = pattern.encode("utf-8")
            if len(pattern_bytes) > 255:
                pattern_bytes = pattern_bytes[:255]
            packet += struct.pack("!B", len(pattern_bytes))
            packet += pattern_bytes

        elif msg_type == "delete_messages":
            # Operation ID = 9
            # [op_id:1] [count:1] [msg_id_1:4] ... [msg_id_N:4]
            message_ids = data.get("message_ids_to_delete", [])
            count = len(message_ids)
            if count > 255:
                count = 255

            packet += struct.pack("!B", count)
            for msg_id in message_ids[:count]:
                packet += struct.pack("!I", msg_id)

        elif msg_type == "delete_account":
            # Operation ID = 10
            # [op_id:1] -> no extra fields
            pass

        elif msg_type == "reset_db":
            # Operation ID = 11
            # [op_id:1] -> no extra fields
            pass

        elif msg_type == "response":
            """
            [op_id=12]
            [success=1 byte]  (0=error, 1=ok)
            [msg_length=2 bytes]
            [msg= msg_length bytes, UTF-8]
            """
            success_flag = 1 if data.get("status") == "ok" else 0
            msg_bytes = data.get("msg", "").encode("utf-8")
            msg_len = len(msg_bytes)
            if msg_len > 65535:  # Ensure it fits in 2 bytes
                msg_bytes = msg_bytes[:65535]
                msg_len = 65535

            packet += struct.pack("!B", success_flag)  # 1 byte
            packet += struct.pack("!H", msg_len)  # 2 bytes for length
            packet += msg_bytes  # Message content

        elif msg_type == "failure":
            """
            [op_id=255]
            [error_len=2 bytes]
            [error_message: error_len bytes (UTF-8)]
            """
            error_msg = data.get("error_message", "unknown failure").encode("utf-8")
            error_len = len(error_msg)
            if error_len > 65535:  # Ensure it fits in 2 bytes
                error_msg = error_msg[:65535]
                error_len = 65535

            packet += struct.pack("!H", error_len)  # 2 bytes for length
            packet += error_msg  # Error message content


        else:
            # Unrecognized or not implemented
            pass

        return packet
    ############################################################
    # Internal helper: _decode_packet
    ############################################################

    def _decode_packet(self, conn, op_id, msg_type):
        """
        Read the rest of the packet from the socket,
        parse fields according to the operation ID, 
        and return a dict `data`.
        """
        data = {}

        if msg_type == "signup":
            # [op_id:1] [username_len:1] [username] [password_len:1] [password]
            user_len = self._recv_exact(conn, 1)
            if not user_len: return None
            user_len = user_len[0]

            username = self._recv_exact(conn, user_len)
            if not username: return None
            username_str = username.decode("utf-8")

            pass_len = self._recv_exact(conn, 1)
            if not pass_len: return None
            pass_len = pass_len[0]

            password = self._recv_exact(conn, pass_len)
            if not password: return None
            password_str = password.decode("utf-8")

            data["username"] = username_str
            data["password"] = password_str

        elif msg_type == "login":
            # [op_id:1] [username_len:1] [username] [password_len:1] [password] [unread_count:4]
            ul_raw = self._recv_exact(conn, 1)
            if not ul_raw: return None
            ulen = ul_raw[0]

            uname = self._recv_exact(conn, ulen)
            if not uname: return None
            username_str = uname.decode("utf-8")

            pl_raw = self._recv_exact(conn, 1)
            if not pl_raw: return None
            plen = pl_raw[0]

            pw = self._recv_exact(conn, plen)
            if not pw: return None
            password_str = pw.decode("utf-8")

            # ✅ Fix: Read unread_count as a 4-byte integer
            ur_raw = self._recv_exact(conn, 4)
            if not ur_raw: return None
            unread_count = int.from_bytes(ur_raw, byteorder="big")  # Convert bytes to integer

            data["username"] = username_str
            data["password"] = password_str
            data["unread_count"] = unread_count  # ✅ Now properly assigned

        elif msg_type == "logout":
            # [op_id:1] -> no extra fields
            pass

        elif msg_type == "count_unread":
            # [op_id:1] -> no extra fields
            pass

        elif msg_type == "send_message":
            # [op_id=5]
            # [sender_len:1][sender]
            # [recipient_len:1][recipient]
            # [msg_len:2][message]
            
            slen_raw = self._recv_exact(conn, 1)
            if not slen_raw: return None
            slen = slen_raw[0]
            sender_bytes = self._recv_exact(conn, slen)
            if not sender_bytes: return None
            sender_str = sender_bytes.decode("utf-8")

            rlen_raw = self._recv_exact(conn, 1)
            if not rlen_raw: return None
            rlen = rlen_raw[0]
            recipient_bytes = self._recv_exact(conn, rlen)
            if not recipient_bytes: return None
            recipient_str = recipient_bytes.decode("utf-8")

            msg_len_raw = self._recv_exact(conn, 2)
            if not msg_len_raw: return None
            (msg_len,) = struct.unpack("!H", msg_len_raw)
            content_bytes = self._recv_exact(conn, msg_len)
            if not content_bytes: return None
            content_str = content_bytes.decode("utf-8")

            data["sender"] = sender_str
            data["recipient"] = recipient_str
            data["content"] = content_str

        elif msg_type == "send_messages_to_client":
            # [op_id:1] -> no extra fields
            pass

        elif msg_type == "fetch_away_msgs":
            # [op_id:1] [limit:1]
            limit_raw = self._recv_exact(conn, 1)
            if not limit_raw: return None
            data["limit"] = limit_raw[0]

        elif msg_type == "list_accounts":
            # [op_id:1] [count:1] [start:4] [pattern_len:1] [pattern_bytes]
            cnt_raw = self._recv_exact(conn, 1)
            if not cnt_raw: return None
            count_val = cnt_raw[0]

            start_raw = self._recv_exact(conn, 4)
            if not start_raw: return None
            (start_val,) = struct.unpack("!I", start_raw)

            pat_len_raw = self._recv_exact(conn, 1)
            if not pat_len_raw: return None
            pat_len = pat_len_raw[0]

            pattern_bytes = b""
            if pat_len > 0:
                p = self._recv_exact(conn, pat_len)
                if not p: return None
                pattern_bytes = p

            data["count"]   = count_val
            data["start"]   = start_val
            data["pattern"] = pattern_bytes.decode("utf-8")

        elif msg_type == "delete_messages":
            # [op_id:1] [count:1] [msg_id_1:4] ... [msg_id_N:4]
            c_raw = self._recv_exact(conn, 1)
            if not c_raw: return None
            cval = c_raw[0]

            msg_ids = []
            for _ in range(cval):
                chunk = self._recv_exact(conn, 4)
                if not chunk: return None
                (mid,) = struct.unpack("!I", chunk)
                msg_ids.append(mid)

            data["message_ids_to_delete"] = msg_ids

        elif msg_type == "delete_account":
            # [op_id:1] -> no extra fields
            pass

        elif msg_type == "reset_db":
            # [op_id:1] -> no extra fields
            pass

        # ---------- response (12) ----------
        elif msg_type == "response":
            """
            [op_id=12]
            [success=1 byte]  (0=error, 1=ok)
            [msg_length=2 bytes]
            [msg= msg_length bytes, UTF-8]
            """
            success_raw = self._recv_exact(conn, 1)
            if not success_raw:
                return None
            success_flag = success_raw[0]

            msg_len_raw = self._recv_exact(conn, 2)
            if not msg_len_raw:
                return None
            (msg_len,) = struct.unpack("!H", msg_len_raw)

            # Receive 'msg_len' bytes, then decode to UTF-8
            resp_bytes = self._recv_exact(conn, msg_len)
            if not resp_bytes:
                return None
            resp_str = resp_bytes.decode("utf-8")

      
            data["status"] = "ok" if success_flag == 1 else "error"
            data["msg"]    = resp_str
        

        # ---------- failure (255) ----------
        elif msg_type == "failure":
            """
            [op_id=255]
            [error_len=2 bytes]
            [error_message: error_len bytes (UTF-8)]
            """
            elen_raw = self._recv_exact(conn, 2)
            if not elen_raw:
                return None
            (error_len,) = struct.unpack("!H", elen_raw)

            err_bytes = self._recv_exact(conn, error_len)
            if not err_bytes:
                return None
            err_str = err_bytes.decode("utf-8")

            data["error_message"] = err_str

        else:
            # Unknown or unimplemented
            return None

        return data


    ############################################################
    # Utility: _recv_exact
    ############################################################

    def _recv_exact(self, conn, nbytes):
        """
        Read exactly 'nbytes' bytes from the socket.
        Return None if we cannot (connection closed).
        """
        buf = bytearray()
        while len(buf) < nbytes:
            chunk = conn.recv(nbytes - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)
