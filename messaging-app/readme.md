## JoChat  
JoChat is a distributed messaging system that supports user authentication, message delivery, and account management.

## Quick Setup & Deployment  
To set up and run JoChat, follow these steps in a **fresh virtual environment** (for the love of that which is holy):
You can find your local network's ip address by doing ifconfig.
```
pip install -r requirements.txt
make run-server  # (optional arguments: --host 0.0.0.0 --port 5000 --protocol json/binary)``
make run-client  # (optional arguments: --host 0.0.0.0 --port 5000 --protocol json/binary)``
```

An example:
```
make run-client CLIENT_ARGS="--protocol custom"
make run-server SERVER_ARGS="--port 5001 --debug"
or simply
make run-all SERVER_ARGS="--port 5001" CLIENT_ARGS="--protocol custom"
```

This will spin up a **Streamlit web application**, allowing you to:  
- Sign up and log in  
- See the number of unread messages while you were away  
- Send messages to other users  
- List accounts matching a wildcard pattern (with pagination)  
- Delete your account  
- Log out  

## 📂 Project Directory Structure 
``` 
messaging-app/
│── client/                        # Client-side implementation
│   │── client.py                   # Main client script
│   │── test_suite_client/           # Test suite for client-side functionality
│── protocol/                        # Protocol implementation
│   │── protocol.py                   # Custom binary wire protocol implementation
│   │── spec.md                       # Detailed specification of the wire protocol
│── server/                        # Server-side implementation
│   │── server.py                   # Main server script
│   │── actions.py                  # Handles server-side actions
│   │── database.py                  # Database interaction functions
│   │── chat.db                      # SQLite database for storing users and messages
│   │── chat.db-journal              # SQLite journal file for database transactions
│   │── test_suite_server/           # Test suite for server-side functionality
│── Makefile                        # Automation for running server, client, and tests
│── readme.md                       # Project documentation
│── requirements.txt                 # Dependencies required for the project
```

## Code Documentation

### The Server
The server is the **backbone** of JoChat.

- Uses **sockets** to allow multiple clients to communicate concurrently.
- Stores user accounts and messages in **SQLite (`chat.db`)**, keeping track of:
  - **Sender**
  - **Recipient**
  - **Message content**
  - **Delivery status**
- Messages sent while the recipient is offline are marked as **"sent while away"**, ensuring delivery when they log back in.
- Uses a **threading model**, where each connected client is handled in a separate thread with a separate action queue.
- Implements a **request-response model**, where clients send requests (e.g., `"send_message"`, `"fetch_away_msgs"`, `"delete_account"`), and the server responds with data or status updates.
- The server processes actions using a **queue per client**.
- **Concurrency control:** Implements a **coarse-grained locking mechanism**, where basically a server can handle one client action at a time, but does not need to finish one user's action queue before moving on.
- **Security:** Passwords are **hashed using SHA-256** before transmission on the client side. Clients are responsible for hashing their passwords.
### The Client 

The client side is handled entirely with the file `client.py` with modular design and a clean interface, with ChatServerClient and StreamlitChatApp classes (the former handling server connection behavior and the latter handling the Streamlit UI for a pleasant and aesthetic user experience).  Ultimately, the client is responsible for:

- **User Interface**: Providing a user-friendly interface for users to interact with the server.
- **Handling User Input**: Sending user input to the server and displaying server responses.
- **Displaying Messages**: Showing messages from other users in real-time.
- **Ensuring Structured Communication**: Sending and receiving messages in the correct format and protocol (JSON or binary).

#### Client-server connection

For client-server connection, the `ChatServerClient` class is responsible for maintaining a persistent connection with the server using TCP sockets. It sends structured requests to the server and receives responses. Upon initialization with the host, port, and protocol specified, it connects to the server for communication, doing so via the following methods:

- **`__init__`**: initializes the client with the server's host, port, and protocol
- **`_get_socket`**: establishes a connection with the server using TCP sockets
- **`send_request`**: builds a request message and sends it to the server (with `is_response` flag set to `0`), returning the server's response data
- **`hash_password`**: hashes user's UTF-8-encoded password using SHA-256

#### Streamlit UI

The `StreamlitChatApp` class is the main application page for the Streamlit user interface and app (and is the bulk of the `client.py` file), providing a clean and aesthetic interface for users to interact with the server. It uses Streamlit to create a web-based UI that allows users to send messages, view messages from other users, etc, and provides helpful warnings that display brief feedback messages to the user by way of the project's error-handling mechanisms. The class includes the following methods:

- **`__init__`**: initializes the Streamlit app with the server's host, port, protocol, and client by way of the `ChatServerClient` class
- **`_initialize_session_state`**: initializes the session state for the Streamlit app for cached access to user and client data that persists across app reruns. This includes the user's username, password, and messages, etc. Note that this is a Streamlit-specific method whose application here is **not** to replace a database or replace server-side storage, but to provide a temporary cache for the client-side app since Streamlit is stateless.
- **`_update_unread_count`**: helper method to update the unread message count in the Streamlit app via call/request to the server, updating the session state with the new count
- **`_show_login_or_signup_page`**: displays the login or signup page based on the user's current state (logged in or not).
[Other analogous pages for the app are similarly defined, such as `show_home_page`, `show_send_message_page`, `show_inbox_page`, `show_list_accounts_page`, `show_logout_page`, etc.]
- **`run_app`**: main entry point for the Streamlit app, running the app and displaying the appropriate page based on the user's current state and actions

Overall, the UI is designed to provide a real-time messaging experience with features like an unread message counter, dynamically updated inbox, and user authentication management. All pages are accessible at any time via the sidebar, and each session operates under a single logged-in user to ensure session integrity.

### For the **custom binary protocol**, refer to [`spec.md`](spec.md) ' in the protocol folder.


### Testing & Quality Assurance 
JoChat includes a comprehensive unit test suite, and has undergone integration testing. 

#### Running Tests  

To run server-side tests, `cd` into the test_suite_server folder and execute the following command:  
```bash
python -m unittest
```
To run client-side tests, `cd` into the test_suite_client folder and execute the following command:  
```bash
python -m unittest
```

Easy as pie.

### What is Tested?  

- **Server Tests (`test_suite_server/`)**
  - User login and authentication
  - Message sending and retrieval
  - Account creation and deletion
  - Database consistency
  - In a suite of 45+ tests.
- **Client Tests (`test_suite_client/`)**
  - Connection handling  
  - Sending and receiving messages  
  - UI interactions
  
## Custom Protocol Implementation  

JoChat supports **two wire protocols**:  

1. **JSON Protocol**   
2. **Custom Binary Protocol** (reduced bandwidth)  

Every message in the **custom protocol** follows this structure:  

1. **Operation ID (1 byte)** – Identifies the request/response type.  
2. **is_response flag (1 byte)** – `0` for requests, `1` for responses.  
3. **Payload** – Contains message-specific fields as described in [`spec.md`](spec.md).  

Happy messaging on JoChat.
Dries and Jo.
```