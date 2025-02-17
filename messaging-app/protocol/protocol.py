import struct
import json

DEBUG_FLAG = False

###############################################################################
# Message Class
###############################################################################
class Message:
    """Represents a generic message with a type and data payload."""
    def __init__(self, msg_type, data):
        self.msg_type = msg_type  # e.g. "login", "send_message", etc.
        self.data = data          # For responses, you may include "status":"ok"/"error", "msg", etc.

    def __repr__(self):
        return f"<Message type={self.msg_type}, data={self.data}>"

###############################################################################
# JSONProtocolHandler (fallback)
###############################################################################
class JSONProtocolHandler:
    """Encodes and decodes messages as JSON with a 4-byte length prefix."""
    def send(self, conn, message: Message, is_response=False):
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

###############################################################################
# CustomProtocolHandler
###############################################################################
class CustomProtocolHandler:
    """
    Converts between Message objects and our custom binary format:
    
      [op_id:1 byte][is_response:1 byte] + [payload...]
    
    Where op_id is the operation code (1=signup, 2=login, ... 11=reset_db),
    and is_response is (0=request, 1=response).
    
    For requests, parse the relevant fields. For responses, we typically parse:
      [success:1 byte] (1=ok, 0=error)
      If success=1, parse success-specific fields; if success=0, parse error reason.
      Optionally, a "msg" field can be appended, as a [msg_len:1 byte][msg UTF-8].
    """
    def __init__(self):
        self.op_to_name = {
            1:  "signup",
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
            255:"failure"  # fallback
        }
        self.name_to_op = {v:k for k,v in self.op_to_name.items()}

    ###########################################################################
    # Public: send() / receive()
    ###########################################################################
    def send(self, conn, message: Message, is_response: bool):
        """
        Encodes a Message (with a known msg_type) into the custom wire format:
          [op_id:1 byte][is_response:1 byte][payload...]
        """
        op_id = self.name_to_op.get(message.msg_type, 255)  # fallback: 255 => failure
        if DEBUG_FLAG:
            print('op_id', op_id)
            print(f"Sending message: msg_type={message.msg_type}, op_id={op_id}, is_response={is_response}")
        payload = self._encode_payload(message.msg_type, is_response, message.data)
        header = struct.pack("!B", op_id) + struct.pack("!B", 1 if is_response else 0)
        packet = header + payload
        if DEBUG_FLAG:
            print(f"Packet to send: {packet}")
            print(len(packet))
        conn.sendall(packet)

    def receive(self, conn):
        """
        Reads 2 bytes for [op_id, is_response], then decodes payload accordingly.
        Returns a Message object or None on error/closed.
        """
        
        header = self._recv_exact(conn, 2)
        if not header:
            return None
        op_id, resp_flag = struct.unpack("!BB", header)
        is_response = (resp_flag == 1)
        msg_type = self.op_to_name.get(op_id, "unknown")
        if DEBUG_FLAG:
            print('the header is', header)
            print(f"Received message: op_id={op_id}, msg_type={msg_type}, is_response={is_response}")

        data = self._decode_payload(conn, msg_type, is_response)
        if data is None:
            return None # return an empty message if fails to decode
        return Message(msg_type, data)

    ###########################################################################
    # Internal: _encode_payload
    ###########################################################################
    def _encode_payload(self, msg_type: str, is_response: bool, data: dict):
        """
        Build the payload portion (everything after [op_id, is_response]).
        Requests and responses have different formats per operation.
        """
        packet = b""
        if not is_response:
            # ------------------ REQUEST ENCODING ------------------
            if msg_type == "signup":
                # [username_len:1][username][password_len:1][password]
                username = data.get("username", "")
                password = data.get("password", "")
                u_bytes = username.encode("utf-8")
                p_bytes = password.encode("utf-8")
                packet += struct.pack("!B", len(u_bytes)) + u_bytes
                packet += struct.pack("!B", len(p_bytes)) + p_bytes

            elif msg_type == "login":
                # example: [username_len:1][username][pw_len:1][pw]
                username = data.get("username", "")
                password = data.get("password", "")
                u_bytes = username.encode("utf-8")
                p_bytes = password.encode("utf-8")
                packet += struct.pack("!B", len(u_bytes)) + u_bytes
                packet += struct.pack("!B", len(p_bytes)) + p_bytes

            elif msg_type == "logout":
                pass

            elif msg_type == "count_unread":
                pass

            elif msg_type == "send_message":
                # [sender_len:1][sender][recipient_len:1][recipient][msg_len:2][message]
                sender = data.get("sender", "")
                recipient = data.get("recipient", "")
                content = data.get("content", "")
                s_bytes = sender.encode("utf-8")
                r_bytes = recipient.encode("utf-8")
                c_bytes = content.encode("utf-8")
                packet += struct.pack("!B", len(s_bytes)) + s_bytes
                packet += struct.pack("!B", len(r_bytes)) + r_bytes
                packet += struct.pack("!H", len(c_bytes)) + c_bytes

            elif msg_type == "send_messages_to_client":
                pass

            elif msg_type == "fetch_away_msgs":
                # [limit:1]
                limit = data.get("limit", 10)
                if limit > 255:
                    limit = 255
                packet += struct.pack("!B", limit)


            elif msg_type == "list_accounts":
                # Request layout:
                #   [count:1][start:4][pattern_len:1][pattern]
                count_val = data.get("count", 10)
                if count_val > 255:
                    count_val = 255
                start_val = data.get("start", 0)
                pattern_str = data.get("pattern", "")
                pattern_b = pattern_str.encode("utf-8")
                if len(pattern_b) > 255:
                    pattern_b = pattern_b[:255]

                # 1) count (1 byte)
                packet += struct.pack("!B", count_val)
                # 2) start (4 bytes, big-endian)
                packet += struct.pack("!I", start_val)
                # 3) pattern_len (1 byte)
                packet += struct.pack("!B", len(pattern_b))
                # 4) pattern (pattern_len bytes)
                packet += pattern_b

            elif msg_type == "delete_messages":
                # [count:1][each msg_id:4]
                msg_ids = data.get("message_ids_to_delete", [])
                cnt = len(msg_ids)
                if cnt > 255:
                    cnt = 255
                packet += struct.pack("!B", cnt)
                for mid in msg_ids[:cnt]:
                    packet += struct.pack("!I", mid)

            elif msg_type == "delete_account":
                pass

            elif msg_type == "reset_db":
                pass

            else:
                # fallback/failure?
                pass
        else:
            # ------------------ RESPONSE ENCODING ------------------
            def encode_string_field(msg_text: str) -> bytes:
                """Encodes a short text field as [length:1][UTF-8]."""
                if not msg_text:
                    return struct.pack("!B", 0)
                b = msg_text.encode("utf-8")
                if len(b) > 255:
                    b = b[:255]
                return struct.pack("!B", len(b)) + b

            # We'll interpret data["status"] as "ok" => success=1, else success=0
            success_byte = 1 if data.get("status", "error") == "ok" else 0

            if msg_type == "signup":
                # [success:1][msg]
                packet += struct.pack("!B", success_byte)
                packet += encode_string_field(data.get("msg", ""))

            elif msg_type == "login":
                # [success:1][unread_count:2][msg]
                packet += struct.pack("!B", success_byte)
        
                unread = data.get("unread_count", 0) # if there is no unread_count, give -1 back
                packet += struct.pack("!H", unread)

                packet += encode_string_field(data.get("msg", ""))

            elif msg_type == "logout":
                # [success:1][msg]
                packet += struct.pack("!B", success_byte)
                packet += encode_string_field(data.get("msg", ""))

            elif msg_type == "count_unread":
                # [success:1][unread_count:2][msg]
                packet += struct.pack("!B", success_byte)
                if success_byte == 1:
                    packet += struct.pack("!H", data.get("unread_count", 0))
                else:
                    packet += struct.pack("!H", 0)
                packet += encode_string_field(data.get("msg", ""))

            elif msg_type == "send_message":
                # [success:1][msg]
                packet += struct.pack("!B", success_byte)
                packet += encode_string_field(data.get("msg", ""))

            elif msg_type == "send_messages_to_client":
                """
                If data.get("status") == "ok":
                [success=1]
                [msg_count:1]
                For each message:
                    [id:4][sender_len:1][sender][content_len:2][content]
                Else:
                [success=0]
                [err_len:1][err_utf8]
                """
                success_byte = 1 if data.get("status") == "ok" else 0
                packet += struct.pack("!B", success_byte)

                if success_byte == 1:
                    messages = data.get("msg", [])
                    msg_count = len(messages)
                    if msg_count > 255:
                        msg_count = 255
                    # 1 byte for message count
                    packet += struct.pack("!B", msg_count)

                    for m in messages[:msg_count]:
                        msg_id = m.get("id", 0)
                        sender_str = m.get("sender", "")
                        content_str = m.get("content", "")

                        # ID is 4 bytes
                        packet += struct.pack("!I", msg_id)

                        # Sender
                        sender_bytes = sender_str.encode("utf-8")
                        if len(sender_bytes) > 255:
                            sender_bytes = sender_bytes[:255]
                        packet += struct.pack("!B", len(sender_bytes))
                        packet += sender_bytes

                        # Content
                        content_bytes = content_str.encode("utf-8")
                        content_len = len(content_bytes)
                        packet += struct.pack("!H", content_len)
                        packet += content_bytes

                else:
                    # If error => [err_len:1][err_utf8]
                    err_msg = data.get("msg", "Unknown error")
                    err_bytes = err_msg.encode("utf-8")
                    if len(err_bytes) > 255:
                        err_bytes = err_bytes[:255]
                    packet += struct.pack("!B", len(err_bytes))
                    packet += err_bytes


            elif msg_type == "fetch_away_msgs":
                """
                Proposed format:
                [success:1 byte]
                If success=1 => [msg_count:2 bytes], then for each message:
                   [id:4] [sender_len:1] [sender_bytes] [content_len:2] [content_bytes]
                If success=0 => we encode an error message as [error_len:1][error_utf8]
                success_byte = 1 if data.get("status") == "ok" else 0
                """
                packet += struct.pack("!B", success_byte)

                if success_byte == 1:
                    messages = data.get("msg", [])
                    msg_count = len(messages)
                    # 2-byte big-endian integer for number of messages:
                    packet += struct.pack("!H", msg_count)
                    for msg in messages:
                        msg_id = msg.get("id", 0)
                        sender = msg.get("sender", "")
                        content = msg.get("content", "")

                        packet += struct.pack("!I", msg_id)  # 4-byte ID

                        s_bytes = sender.encode("utf-8")
                        if len(s_bytes) > 255:
                            s_bytes = s_bytes[:255]          # Trim if needed
                        packet += struct.pack("!B", len(s_bytes)) + s_bytes

                        c_bytes = content.encode("utf-8")
                        packet += struct.pack("!H", len(c_bytes)) + c_bytes
                else:
                    # Error case => define an error string
                    err_str = data.get("msg", "Unknown error")
                    err_bytes = err_str.encode("utf-8")
                    if len(err_bytes) > 255:
                        err_bytes = err_bytes[:255]
                    packet += struct.pack("!B", len(err_bytes)) + err_bytes


            elif msg_type == "list_accounts":
                """
                If status="ok":

                [success:1] → 1
                [acct_count:1]
                For each account:
                [acct_id:4]
                [uname_len:1]
                [uname (UTF-8, up to 255 bytes)]
                If status="error":

                [success:1] → 0
                [err_len:1]
                [err_utf8 (up to 255 bytes)]
                """
                success_byte = 1 if data.get("status") == "ok" else 0
                packet += struct.pack("!B", success_byte)

                if success_byte == 1:
                    # 2) account count (1 byte)
                    accounts = data.get("users", [])
                    count = min(len(accounts), 255)
                    packet += struct.pack("!B", count)

                    # 3) For each account => [id:4][uname_len:1][uname_utf8]
                    for (acct_id, uname) in accounts[:count]:
                        uname_b = uname.encode("utf-8")[:255]
                        packet += struct.pack("!I", acct_id)
                        packet += struct.pack("!B", len(uname_b))
                        packet += uname_b
                else:
                    # Error => [err_len:1][err_utf8]
                    error_msg = data.get("msg", "Unknown error")
                    err_bytes = error_msg.encode("utf-8")[:255]
                    packet += struct.pack("!B", len(err_bytes))
                    packet += err_bytes


            elif msg_type == "delete_messages":
                # [success:1] if success => [deleted_count:1], then a final msg field
                packet += struct.pack("!B", success_byte)
                if success_byte == 1:
                    deleted_cnt = data.get("deleted_count", 0)
                    packet += struct.pack("!B", deleted_cnt)
                packet += encode_string_field(data.get("msg", ""))

            elif msg_type == "delete_account":
                # [success:1][msg]
                packet += struct.pack("!B", success_byte)
                packet += encode_string_field(data.get("msg", ""))

            elif msg_type == "reset_db":
                # [success:1][msg]
                packet += struct.pack("!B", success_byte)
                packet += encode_string_field(data.get("msg", ""))

            elif msg_type == "failure":
                # [error_len:2][error_message]
                err_b = data.get("error_message", "unknown failure").encode("utf-8")
                if len(err_b) > 65535:
                    err_b = err_b[:65535]
                packet += struct.pack("!H", len(err_b))
                packet += err_b

            else:
                pass

        return packet

    ###########################################################################
    # Internal: _decode_payload
    ###########################################################################
    def _decode_payload(self, conn, msg_type, is_response):
        """Reads payload fields after op_id + is_response and returns a data dict."""
        data = {}
        if not is_response:
            # ----------------- REQUEST DECODING -----------------
            if msg_type == "signup":
                # [username_len:1][username][password_len:1][password]
                ulen_b = self._recv_exact(conn, 1)
                if not ulen_b:
                    return None
                ulen = ulen_b[0]
                uname_bytes = self._recv_exact(conn, ulen)
                if not uname_bytes:
                    return None
                username = uname_bytes.decode("utf-8")

                plen_b = self._recv_exact(conn, 1)
                if not plen_b:
                    return None
                plen = plen_b[0]
                pw_bytes = self._recv_exact(conn, plen)
                if not pw_bytes:
                    return None
                password = pw_bytes.decode("utf-8")

                data["username"] = username
                data["password"] = password

            elif msg_type == "login":
                # [username_len:1][username][password_len:1][password]
                ulen_b = self._recv_exact(conn, 1)
                if not ulen_b:
                    return None
                ulen = ulen_b[0]
                uname_bytes = self._recv_exact(conn, ulen)
                if not uname_bytes:
                    return None
                username = uname_bytes.decode("utf-8")

                plen_b = self._recv_exact(conn, 1)
                if not plen_b:
                    return None
                plen = plen_b[0]
                pw_bytes = self._recv_exact(conn, plen)
                if not pw_bytes:
                    return None
                password = pw_bytes.decode("utf-8")
                data["username"] = username
                data["password"] = password

            elif msg_type == "logout":
                pass

            elif msg_type == "count_unread":
                pass

            elif msg_type == "send_message":
                slen_b = self._recv_exact(conn, 1)
                if not slen_b:
                    return None
                slen = slen_b[0]
                s_bytes = self._recv_exact(conn, slen)
                if not s_bytes:
                    return None
                sender = s_bytes.decode("utf-8")

                rlen_b = self._recv_exact(conn, 1)
                if not rlen_b:
                    return None
                rlen = rlen_b[0]
                r_bytes = self._recv_exact(conn, rlen)
                if not r_bytes:
                    return None
                recipient = r_bytes.decode("utf-8")

                msg_len_b = self._recv_exact(conn, 2)
                if not msg_len_b:
                    return None
                (msg_len,) = struct.unpack("!H", msg_len_b)
                content_bytes = self._recv_exact(conn, msg_len)
                if not content_bytes:
                    return None
                content = content_bytes.decode("utf-8")

                data["sender"] = sender
                data["recipient"] = recipient
                data["content"] = content

            elif msg_type == "send_messages_to_client":
                pass

            elif msg_type == "fetch_away_msgs":
                limit_b = self._recv_exact(conn, 1)
                if not limit_b:
                    return None
                data["limit"] = limit_b[0]


            elif msg_type == "list_accounts":
                # [count:1][start:4][pattern_len:1][pattern UTF-8]
                c_b = self._recv_exact(conn, 1)
                if not c_b: return None
                count_val = c_b[0]

                start_b = self._recv_exact(conn, 4)
                if not start_b: return None
                (start_val,) = struct.unpack("!I", start_b)

                pat_len_b = self._recv_exact(conn, 1)
                if not pat_len_b: return None
                pat_len = pat_len_b[0]

                pat_bytes = b""
                if pat_len > 0:
                    pat_bytes = self._recv_exact(conn, pat_len)
                    if not pat_bytes: return None

                data["count"] = count_val
                data["start"] = start_val
                data["pattern"] = pat_bytes.decode("utf-8")


            elif msg_type == "delete_messages":
                c_b = self._recv_exact(conn, 1)
                if not c_b:
                    return None
                cval = c_b[0]
                msg_ids = []
                for _ in range(cval):
                    id_b = self._recv_exact(conn, 4)
                    if not id_b:
                        return None
                    (mid,) = struct.unpack("!I", id_b)
                    msg_ids.append(mid)
                data["message_ids_to_delete"] = msg_ids

            elif msg_type == "delete_account":
                pass

            elif msg_type == "reset_db":
                pass

            elif msg_type == "failure":
                # fallback
                elen_b = self._recv_exact(conn, 2)
                if not elen_b:
                    return None
                (elen,) = struct.unpack("!H", elen_b)
                err_b = self._recv_exact(conn, elen)
                if not err_b:
                    return None
                data["error_message"] = err_b.decode("utf-8")

            else:
                # unknown request
                return None

        else:
            # ----------------- RESPONSE DECODING -----------------
            # We'll interpret the first byte as success=1 or 0
            # Then decode operation-specific fields accordingly.
            def read_string_field():
                length_b = self._recv_exact(conn, 1)
                if not length_b:
                    return None
                length_val = length_b[0]
                if length_val == 0:
                    return ""
                txt_b = self._recv_exact(conn, length_val)
                if not txt_b:
                    return None
                return txt_b.decode("utf-8")

            if msg_type == "signup":
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                success = success_b[0]
                data["status"] = "ok" if success == 1 else "error"
                msg_str = read_string_field()
                if msg_str is None:
                    return None
                data["msg"] = msg_str

            elif msg_type == "login":
                # [success:1][unread_count:2][msg]
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                success = success_b[0]
                data["status"] = "ok" if success == 1 else "error"

                unread_raw = self._recv_exact(conn, 2)
                if not unread_raw:
                    return None
                (unread_count,) = struct.unpack("!H", unread_raw)
                data["unread_count"] = unread_count

                msg_str = read_string_field()
                if msg_str is None:
                    return None
                data["msg"] = msg_str

            elif msg_type == "logout":
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                data["status"] = "ok" if success_b[0] == 1 else "error"
                msg_str = read_string_field()
                if msg_str is None:
                    return None
                data["msg"] = msg_str

            elif msg_type == "count_unread":
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                success = success_b[0]
                data["status"] = "ok" if success == 1 else "error"

                unread_raw = self._recv_exact(conn, 2)
                if not unread_raw:
                    return None
                (unread_count,) = struct.unpack("!H", unread_raw)
                data["unread_count"] = unread_count

                msg_str = read_string_field()
                if msg_str is None:
                    return None
                data["msg"] = msg_str

            elif msg_type == "send_message":
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                data["status"] = "ok" if success_b[0] == 1 else "error"
                msg_str = read_string_field()
                if msg_str is None:
                    return None
                data["msg"] = msg_str

            elif msg_type == "send_messages_to_client":
                """
                [success:1]
                If success=1:
                [msg_count:1]
                For each message => [id:4][sender_len:1][sender_utf8][content_len:2][content_utf8]
                Else:
                [err_len:1][err_utf8]
                """

                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                success = success_b[0]
                data["status"] = "ok" if success == 1 else "error"

                if success == 1:
                    # read msg_count
                    msg_count_b = self._recv_exact(conn, 1)
                    if not msg_count_b:
                        return None
                    msg_count = msg_count_b[0]

                    msgs = []
                    for _ in range(msg_count):
                        # [id:4]
                        id_b = self._recv_exact(conn, 4)
                        if not id_b:
                            return None
                        (mid,) = struct.unpack("!I", id_b)

                        # [sender_len:1]
                        slen_b = self._recv_exact(conn, 1)
                        if not slen_b:
                            return None
                        slen = slen_b[0]
                        # [sender_utf8]
                        s_bytes = self._recv_exact(conn, slen)
                        if not s_bytes:
                            return None
                        sender_str = s_bytes.decode("utf-8")

                        # [content_len:2]
                        clen_b = self._recv_exact(conn, 2)
                        if not clen_b:
                            return None
                        (clen,) = struct.unpack("!H", clen_b)
                        # [content_utf8]
                        content_bytes = self._recv_exact(conn, clen)
                        if not content_bytes:
                            return None
                        content_str = content_bytes.decode("utf-8")

                        msgs.append({
                            "id": mid,
                            "sender": sender_str,
                            "content": content_str
                        })
                    data["msg"] = msgs

                else:
                    # error => read [err_len:1][err_utf8]
                    err_len_b = self._recv_exact(conn, 1)
                    if not err_len_b:
                        return None
                    err_len = err_len_b[0]
                    if err_len > 0:
                        err_bytes = self._recv_exact(conn, err_len)
                        if not err_bytes:
                            return None
                        data["msg"] = err_bytes.decode("utf-8")
                    else:
                        data["msg"] = ""


            # In the _decode_payload method:
            # fetch away msgs decoding response
            elif msg_type == "fetch_away_msgs":
                # First read [success:1]
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                success = success_b[0]
                data["status"] = "ok" if success == 1 else "error"

                if success == 1:
                    # Next read [msg_count:2]
                    count_b = self._recv_exact(conn, 2)
                    if not count_b:
                        return None
                    (msg_count,) = struct.unpack("!H", count_b)

                    messages = []
                    for _ in range(msg_count):
                        # [id:4]
                        msg_id_b = self._recv_exact(conn, 4)
                        if not msg_id_b:
                            return None
                        (msg_id,) = struct.unpack("!I", msg_id_b)

                        # [sender_len:1] [sender_bytes]
                        slen_b = self._recv_exact(conn, 1)
                        if not slen_b:
                            return None
                        slen = slen_b[0]
                        sender_b = self._recv_exact(conn, slen)
                        if not sender_b:
                            return None
                        sender = sender_b.decode("utf-8")

                        # [content_len:2] [content_bytes]
                        clen_b = self._recv_exact(conn, 2)
                        if not clen_b:
                            return None
                        (clen,) = struct.unpack("!H", clen_b)
                        content_b = self._recv_exact(conn, clen)
                        if not content_b:
                            return None
                        content = content_b.decode("utf-8")

                        messages.append({
                            "id": msg_id,
                            "sender": sender,
                            "content": content
                        })
                    data["msg"] = messages
                else:
                    # Error case => read an error string as [err_len:1][err_utf8]
                    err_len_b = self._recv_exact(conn, 1)
                    if not err_len_b:
                        return None
                    err_len = err_len_b[0]
                    if err_len > 0:
                        err_b = self._recv_exact(conn, err_len)
                        if not err_b:
                            return None
                        data["msg"] = err_b.decode("utf-8")
                    else:
                        data["msg"] = ""

                # data now has "status" and "msg"


            elif msg_type == "list_accounts":
                # Read success
                
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                success = success_b[0]
                data["status"] = "ok" if success == 1 else "error"
                if success == 1:
                    # Read account count
                    count_b = self._recv_exact(conn, 1)
                    if not count_b:
                        return None
                    acct_count = count_b[0]
                    users = []
                    for _ in range(acct_count):
                        # [acct_id:4]
                        id_b = self._recv_exact(conn, 4)
                        if not id_b:
                            return None
                        (acct_id,) = struct.unpack("!I", id_b)
                        # [uname_len:1][uname_utf8]
                        ulen_b = self._recv_exact(conn, 1)
                        if not ulen_b:
                            return None
                        uname_len = ulen_b[0]
                        uname_b = self._recv_exact(conn, uname_len)
                        if not uname_b:
                            return None
                        uname = uname_b.decode("utf-8")
                        users.append((acct_id, uname))

                    data["users"] = users
                    
                else:
                    # error => [err_len:1][err_utf8]
                    err_len_b = self._recv_exact(conn, 1)
                    if not err_len_b:
                        return None
                    err_len = err_len_b[0]
                    err_bytes = self._recv_exact(conn, err_len)
                    if not err_bytes:
                        return None
                    data["msg"] = err_bytes.decode("utf-8")

            elif msg_type == "delete_messages":
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                success = success_b[0]
                data["status"] = "ok" if success == 1 else "error"
                if success == 1:
                    dcount_b = self._recv_exact(conn, 1)
                    if not dcount_b:
                        return None
                    data["deleted_count"] = dcount_b[0]
                msg_str = read_string_field()
                if msg_str is None:
                    return None
                data["msg"] = msg_str

            elif msg_type == "delete_account":
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                data["status"] = "ok" if success_b[0] == 1 else "error"
                msg_str = read_string_field()
                if msg_str is None:
                    return None
                data["msg"] = msg_str

            elif msg_type == "reset_db":
                success_b = self._recv_exact(conn, 1)
                if not success_b:
                    return None
                data["status"] = "ok" if success_b[0] == 1 else "error"
                msg_str = read_string_field()
                if msg_str is None:
                    return None
                data["msg"] = msg_str

            elif msg_type == "failure":
                # [error_len:2][error_bytes]
                elen_b = self._recv_exact(conn, 2)
                if not elen_b:
                    return None
                (elen,) = struct.unpack("!H", elen_b)
                err_b = self._recv_exact(conn, elen)
                if not err_b:
                    return None
                data["error_message"] = err_b.decode("utf-8")

            else:
                return None

        return data

    ###########################################################################
    # Utility: _recv_exact
    ###########################################################################
    def _recv_exact(self, conn, nbytes):
        """
        Reads exactly 'nbytes' bytes from 'conn'. Returns None if the connection
        closes or not enough data arrives.
        """
        buf = bytearray()
        while len(buf) < nbytes:
            chunk = conn.recv(nbytes - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)