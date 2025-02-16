# JoChat  
JoChat is a distributed messaging system that supports user authentication, message delivery, and account management.

## 🚀 Quick Setup & Deployment  
To set up and run JoChat, follow these steps in a **fresh virtual environment**:

```
pip install -r requirements.txt
make run-server  # (optional arguments: --host 0.0.0.0 --port 5000 --protocol json/binary)``
make run-client
```

This will spin up a **Streamlit web application**, allowing you to:  
✔ Sign up and log in  
✔ See the number of unread messages while you were away  
✔ Send messages to other users  
✔ List accounts matching a wildcard pattern (with pagination)  
✔ Delete your account  
✔ Log out  

## 📂 Project Directory Structure 
``` 
messaging-app/
│── test_suite_server/      # Test suite for server-side functionality
│   │── test_1_login.py     # Test for user login functionality
│   │── test_2_signup.py    # Test for user signup functionality
│   │── … (other test cases)
│   │── test_base.py        # Base test class
│   │── test_suite.py       # Runs all tests together
│── test_suite_client/      # Test suite for client-side functionality
│   │── test_1_client_connection.py     # Test for client-server connection
│   │── test_2_login.py     # Test for user login functionality on the client
│   │── … (other test cases)
│   │── test_base.py        # Base test class
│── chat.db                 # SQLite database for storing users and messages
│── client.py               # Client-side script to interact with the server
│── protocol.py             # Custom binary wire protocol implementation
│── server.py               # Main server implementation
│── Makefile                # Automation for running server, client, and tests
│── requirements.txt        # Dependencies required for the project
│── readme.txt              # Basic project documentation
│── test_log.txt            # Logs for test results
│── client_log.txt          # Logs for client interactions
│── database.py             # Database interaction functions
│── spec.md                 # Detailed specification of the wire protocol
```

## Documentation for server, client, and tests.

### 🖥️ The Server (Backend)
The server is the **backbone** of JoChat. It is responsible for:  
- **Handling user authentication**: Sign up, log in, log out.  
- **Managing message delivery**: Ensuring messages reach the intended recipient.  
- **Enforcing session constraints**: Preventing multiple logins from the same account.  

#### 🛠️ Key Features & Implementation Details
- Uses **socket programming** to allow multiple clients to communicate concurrently.  
- Stores user accounts and messages in **SQLite (`chat.db`)**, keeping track of:
  - **Sender**
  - **Recipient**
  - **Message content**
  - **Delivery status**
- Messages sent while the recipient is offline are marked as **"sent while away"**, ensuring delivery when they log back in.
- Uses a **threading model**, where each connected client is handled in a separate thread.
- Implements a **request-response model**, where clients send requests (e.g., `"send_message"`, `"fetch_away_msgs"`, `"delete_account"`), and the server responds with data or status updates.
- The server processes actions using a **queue per client**, polling actions in sequence.
- **Concurrency control:** Implements a **coarse-grained locking mechanism**, allowing multiple clients to be handled simultaneously without conflicts.





### 💻 The Client (Frontend)

#### Client Specification & Design

The client side is handled entirely with the file `client.py` with modular design and a clean interface, with ChatServerClient and StreamlitChatApp classes (the former handling server connection behavior and the latter handling the Streamlit UI for a pleasant and aesthetic user experience).  Ultimately, the client is responsible for:

- **User Interface**: Providing a user-friendly interface for users to interact with the server.
- **Handling User Input**: Sending user input to the server and displaying server responses.
- **Displaying Messages**: Showing messages from other users in real-time.
- **Ensuring Structured Communication**: Sending and receiving messages in the correct format and protocol (JSON or binary).

#### Client-server connection

The `ChatServerClient` class is responsible for maintaining a persistent connection with the server using TCP sockets. It sends structured requests to the server and receives responses. Upon initialization with the host, port, and protocol specified, it connects to the server for communication, doing so via the following methods:

- **`_get_socket`**: Establishes a connection with the server using TCP sockets
- **`send_request`**: Builds a request message and sends it to the server (with `is_response` flag set to `0`), returning the server's response data
- **`hash_password`**: Hashes the user's UTF-8-encoded password using SHA-256


CHATGPT:
The client is responsible for:  
✔ **Maintaining a persistent connection** with the server using **TCP sockets**.  
✔ **Sending structured requests** using **length-prefixed JSON messages**.  
✔ **Ensuring structured communication**, where each request follows this format:  

```json
{
  "msg_type": "login",
  "data": {
    "username": "user123",
    "password": "hashedpassword"
  }
}
```
For the **custom binary protocol**, refer to [`spec.md`](spec.md).
END CHAT



### 🔑 Security 

- **Security:** Passwords are **hashed using SHA-256** before transmission.  





### 🔧 Setting Up the Server & Client
To start the server, run:
```bash
make run-server
```

Alternatively, you can run the server manually with:
```bash
python server.py --host 0.0.0.0 --port 5000 --protocol json
```
(Replace `json` with custom for the binary protocol.)

To start the client, run:
```bash
make run-client
```


### 🧪 Testing & Quality Assurance (DRIES) 

JoChat includes a comprehensive test suite to ensure reliability and correctness.  

### 🛠 Running Tests  

To run server-side tests, `cd` into the test_suite_server folder and execute the following command:  
```bash
python -m unittest
```

To run client-side tests, `cd` into the test_suite_client folder and execute the following command:  
```bash
python -m unittest
```

#### ✅ What is Tested?   ( NEED TO REWORK)

- **Server Tests (`test_suite_server/`)**
  - User login and authentication
  - Message sending and retrieval
  - Account creation and deletion
  - Database consistency  
- **Client Tests (`test_suite_client/`)**
  - Connection handling  
  - Sending and receiving messages  
  - UI interactions