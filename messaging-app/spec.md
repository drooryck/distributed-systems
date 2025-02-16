# Wire Protocol: Chat System

## General Rules

- **Integers.** Integers are encoded in **big-endian** format.
- **Booleans.** Represented as 1-byte integers (1 for true, 0 for false).
- **Strings.** Strings are encoded in UTF-8 and prefixed with a 1-byte (or more) integer specifying their length.
- **Message Structure.** Every message begins with a **1-byte Operation ID**, followed by an **is_response byte** (1 = response, 0 = request).
- **Parsing Strategy.** Messages are parsed field-by-field based on their format; there is no global length field.
- **Versioning.** When modifying message formats, assign new Operation IDs to ensure backward compatibility.

---

## Operation 1: Create Account

### Request
- **Operation ID (1 byte):** `1`
- **Request (1) or Response (0) Byte:** `0`
- **Username Length (1 byte)**
- **Username (String)**
- **Password Hash Length (1 byte)**
- **Password Hash (String)**

### Response
- **Operation ID (1 byte):** `1`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
  - `1` if account creation succeeded.
  - `0` if failed (e.g., username already exists).
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Operation 2: Login

### Request
- **Operation ID (1 byte):** `2`
- **Request (1) or Response (0) Byte:** `0`
- **Username Length (1 byte)**
- **Username (String)**
- **Password Hash Length (1 byte)**
- **Password Hash (String)**

### Response
- **Operation ID (1 byte):** `2`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
  - `1` if login succeeded.
  - `0` if failed.
- **Unread Message Count (2 bytes)**
  - If login failed, this is `0` or `0xFFFF` for an error indicator.
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Operation 3: Logout

### Request
- **Operation ID (1 byte):** `3`
- **Request (1) or Response (0) Byte:** `0`

### Response
- **Operation ID (1 byte):** `3`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
  - `1` if logout succeeded.
  - `0` if client was not logged in.
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Operation 4: Count Unread Messages

### Request
- **Operation ID (1 byte):** `4`
- **Request (1) or Response (0) Byte:** `0`

### Response
- **Operation ID (1 byte):** `4`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
- **Unread Message Count (2 bytes)**
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Operation 5: Send Message

### Request
- **Operation ID (1 byte):** `5`
- **Request (1) or Response (0) Byte:** `0`
- **Sender Length (1 byte)**
- **Sender (String)**
- **Recipient Length (1 byte)**
- **Recipient (String)**
- **Message Length (2 bytes)**
- **Message (String)**

### Response
- **Operation ID (1 byte):** `5`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Operation 6: Retrieve Messages

### Request
- **Operation ID (1 byte):** `6`
- **Request (1) or Response (0) Byte:** `0`

### Response
- **Operation ID (1 byte):** `6`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
- **Message Count (1 byte)**
- **For each message:**
  - **Message ID (4 bytes)**
  - **Sender Length (1 byte)**
  - **Sender (String)**
  - **Message Length (2 bytes)**
  - **Message (String)**
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Operation 7: List Accounts

### Request
- **Operation ID (1 byte):** `7`
- **Request (1) or Response (0) Byte:** `0`
- **Max Accounts (1 byte)**
- **Start Index (4 bytes)**
- **Pattern Length (1 byte)**
- **Pattern (String)**

### Response
- **Operation ID (1 byte):** `7`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
- **Account Count (1 byte)**
- **For each account:**
  - **Account ID (4 bytes)**
  - **Username Length (1 byte)**
  - **Username (String)**
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Operation 8: Delete Messages

### Request
- **Operation ID (1 byte):** `8`
- **Request (1) or Response (0) Byte:** `0`
- **Count (1 byte)**
- **For each message:**
  - **Message ID (4 bytes)**

### Response
- **Operation ID (1 byte):** `8`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
- **Deleted Count (1 byte)**
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Operation 9: Delete Account

### Request
- **Operation ID (1 byte):** `9`
- **Request (1) or Response (0) Byte:** `0`

### Response
- **Operation ID (1 byte):** `9`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Operation 10: Reset Database

### Request
- **Operation ID (1 byte):** `10`
- **Request (1) or Response (0) Byte:** `0`

### Response
- **Operation ID (1 byte):** `10`
- **Request (1) or Response (0) Byte:** `1`
- **Success (1 byte Boolean)**
- **Message Length (1 byte)**
- **Message (String, optional explanatory message)**

---

## Failure Response (Optional)

### Response
- **Operation ID (1 byte):** `255`
- **Request (1) or Response (0) Byte:** `1`
- **Error Message Length (2 bytes)**
- **Error Message (String)**
