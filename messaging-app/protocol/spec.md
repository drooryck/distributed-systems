# Wire Protocol: Chat

## General Rules

- **Integers.** Integers have a fixed byte-length and are encoded in **big-endian** order.
- **Booleans.** Booleans are represented as 1-byte integers (1 for true, 0 for false).
- **Strings.** Strings are encoded in UTF-8. They are not null‐terminated; instead, each string is preceded by a 1-byte integer (or specified length) that indicates its length in bytes.
- Every message begins with a **1-byte Operation ID**. This ID indicates the type of the message.  
- The same Operation ID is used both for requests (client → server) and for responses (server → client), but the formats differ as described below.
- The second byte in each message is an **is_response flag** (`0` for requests, `1` for responses). This flag helps distinguish between incoming and outgoing messages when processing protocol traffic.
- There is **no global message length field**; each message is parsed field‐by‐field based on its specification.
- There are important assumptions on the length of certain things with this format. A username can only be 256 chars long, the unread message count cannot exceed 65536,  messages cannot exceed 65536 bytes, and the number of messages total in the system cannot exceed 2^32 bytes. This should not be an issue.


## Operation 1: Create Account

_Note: When creating an account, the user’s socket is automatically associated with the new account (no subsequent login required)._

### Request
- **Operation ID (1 byte):** `1`
- **Request (0) or Response (1) Byte:** `0`
- **Username Length (1 byte)**
- **Username (String)**
- **Password Hash Length (1 byte)**
- **Password Hash (String)**

### Response
- **Operation ID (1 byte):** `1`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
  - `1` if the account was created successfully.
  - `0` if there was an error (e.g., username already exists).

---

## Operation 2: Login

### Request
- **Operation ID (1 byte):** `2`
- **Request (0) or Response (1) Byte:** `0`
- **Username Length (1 byte)**
- **Username (String)**
- **Password Hash Length (1 byte)**
- **Password Hash (String)**

### Response
- **Operation ID (1 byte):** `2`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
  - `1` if login succeeded.
  - `0` if login failed.
- **Unread Message Count (2 bytes)**
  - A 2-byte unsigned integer.  
  - If login failed, the count can be `0` (or a special value, e.g., `0xFFFFFFFF`).

---

## Operation 3: Logout

### Request
- **Operation ID (1 byte):** `3`
- **Request (0) or Response (1) Byte:** `0`

### Response
- **Operation ID (1 byte):** `3`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
  - `1` if logout succeeded.
  - `0` if the client was not logged in.

---

## Operation 4: Count Unread

### Request
- **Operation ID (1 byte):** `4`
- **Request (0) or Response (1) Byte:** `0`

### Response
- **Operation ID (1 byte):** `4`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
- **Unread Message Count (2 bytes)**
  - A 2-byte integer indicating the number of unread messages.

---

## Operation 5: Send Message

### Request
- **Operation ID (1 byte):** `5`
- **Request (0) or Response (1) Byte:** `0`
- **Sender Length (1 byte)**
- **Sender (String)**
- **Recipient Length (1 byte)**
- **Recipient (String)**
- **Message Length (2 bytes)**
- **Message (String)**

### Response
- **Operation ID (1 byte):** `5`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
  - `1` if the message was stored successfully.
  - `0` if there was an error (e.g., the recipient does not exist).

---

## Operation 6: Send Messages to Client

*(This operation delivers messages that are marked for immediate delivery.)*

### Request
- **Operation ID (1 byte):** `6`
- **Request (0) or Response (1) Byte:** `0`

### Response
- **Operation ID (1 byte):** `6`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
- **Message Count (1 byte)**
- For each message delivered:
  - **Message ID (4 bytes)**
  - **Sender Length (1 byte)**
  - **Sender (String)**
  - **Message Length (2 bytes)**
  - **Message (String)**

---

## Operation 7: Fetch Away Messages

*(This operation fetches offline messages that have not been immediately delivered.)*

### Request
- **Operation ID (1 byte):** `7`
- **Request (0) or Response (1) Byte:** `0`
- **Limit (1 byte)**
  - Maximum number of offline messages to fetch.

### Response
- **Operation ID (1 byte):** `7`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
- **Message Count (1 byte)**
- For each message fetched:
  - **Message ID (4 bytes)**
  - **Sender Length (1 byte)**
  - **Sender (String)**
  - **Message Length (2 bytes)**
  - **Message (String)**

---

## Operation 8: List Accounts

### Request
- **Operation ID (1 byte):** `8`
- **Request (0) or Response (1) Byte:** `0`
- **Count (1 byte)**
  - Maximum number of accounts to list.
- **Start (4 bytes)**
  - The offset index from which to start listing accounts.
- **Pattern Length (1 byte)**
- **Pattern (String)**
  - A search/filter pattern for account usernames (e.g., `%Alice%`).

### Response
- **Operation ID (1 byte):** `8`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
- **Number of Accounts (1 byte)**
- For each account:
  - **Account ID (4 bytes)**
  - **Username Length (1 byte)**
  - **Username (String)**

---

## Operation 9: Delete Messages

### Request
- **Operation ID (1 byte):** `9`
- **Request (0) or Response (1) Byte:** `0`
- **Count (1 byte)**
  - The number of message IDs to delete (maximum 255).
- For each message to delete:
  - **Message ID (4 bytes)**

### Response
- **Operation ID (1 byte):** `9`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
- **Deleted Message Count (1 byte)**
  - The number of messages successfully deleted.

---

## Operation 10: Delete Account

### Request
- **Operation ID (1 byte):** `10`
- **Request (0) or Response (1) Byte:** `0`

### Response
- **Operation ID (1 byte):** `10`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**

---

## Operation 11: Reset Database

### Request
- **Operation ID (1 byte):** `11`
- **Request (0) or Response (1) Byte:** `0`

### Response
- **Operation ID (1 byte):** `11`
- **Request (0) or Response (1) Byte:** `1`
- **Success (1 byte Boolean)**
  - `1` if the database was reset successfully.
  - `0` if there was an error.

---

## Failure Response (Optional - Operation ID 255)

*(This response is used when an unexpected error occurs or an unknown request is received.)*

### Response
- **Operation ID (1 byte):** `255`
- **Request (0) or Response (1) Byte:** `1`