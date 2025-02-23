## JoChat  
JoChat is a distributed messaging system that supports user authentication, message delivery, and account management.

This version of JoChat works with gRPC, so no longer a need to specify a messaging protocol.

## Quick Setup & Deployment  
To set up and run JoChat, follow these steps in a **fresh virtual environment** (for the love of that which is holy):
You can find your local network's ip address by doing ifconfig. Get
```
pip install -r requirements.txt
make run-server  SERVER_ARGS=" # (optional arguments: --host 0.0.0.0 --port 5000)`` "
make run-client  CLIENT_ARGS = " # (optional arguments: --host 0.0.0.0 --port 5000)`` " 
```

An example:
```
make run-client CLIENT_ARGS="--ip 0.0.0.1"
make run-server SERVER_ARGS="--port 5001"
or simply
make run-all SERVER_ARGS="--port 5001" CLIENT_ARGS=""
```

If you are confused, run
```
make run-server SERVER_ARGS="--help"
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
│   │── chat_service.proto           # gRPC protocol, message definitions.
│── server/                        # Server-side implementation
│   │── server.py                   # Main server script
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
- Messages sent while the recipient is offline are marked as **"sent while away"**, ensuring delivery when they log back in can happen manually.
- Implements a **request-response model**, where clients send requests (e.g., `"send_message"`, `"fetch_away_msgs"`, `"delete_account"`), and the server responds with data or status updates. This corresponds to the "simple gRPC" paradigm.
- The server processes actions using one thread per action it does at a time.
- **Concurrency control:** Implements a **coarse-grained locking mechanism**, where basically a server can handle requests in any order it wants.
- **Security:** Passwords are **hashed using SHA-256** before transmission on the client side. Clients are responsible for hashing their passwords.
### The Client 

The client side is handled entirely with the file `client.py` with modular design and a clean interface, with ChatServerClient and StreamlitChatApp classes (the former handling server connection behavior and the latter handling the Streamlit UI for a pleasant and aesthetic user experience).  Ultimately, the client is responsible for:

- **User Interface**: Providing a user-friendly interface for users to interact with the server.
- **Handling User Input**: Sending user input to the server and displaying server responses.
- **Displaying Messages**: Showing messages from other users in real-time.
- **Ensuring Structured Communication**: Sending and receiving messages in the correct format and protocol (gRPC).

#### Client-server connection
The ChatServerClient class encapsulates the client–server connection using gRPC rather than raw TCP sockets. It handles creating a gRPC channel, sending requests to the server through generated stubs, and receiving structured protobuf responses. Its key methods and responsibilities are:


- **`__init__`**: Initializes the client with the server’s host and port. It sets up a gRPC channel and stores references to any generated stubs (ChatServiceStub) for making requests.

- **`hash_password`**: Hashes a user’s UTF-8-encoded password using SHA-256 before sending it to the server (to avoid storing plain-text passwords).

By relying on gRPC, the client no longer needs to manage its own sockets or parse raw byte streams—all message handling is taken care of by the protobuf definitions and the generated gRPC code.

#### Streamlit UI

The `StreamlitChatApp` class is the main application page for the Streamlit user interface and app (and is the bulk of the `client.py` file), providing a clean and aesthetic interface for users to interact with the server. It uses Streamlit to create a web-based UI that allows users to send messages, view messages from other users, etc, and provides helpful warnings that display brief feedback messages to the user by way of the project's error-handling mechanisms. The class includes the following methods:

- **`__init__`**: initializes the Streamlit app with the server's host, port, protocol, and client by way of the `ChatServerClient` class
- **`_initialize_session_state`**: initializes the session state for the Streamlit app for cached access to user and client data that persists across app reruns. This includes the user's username, password, and messages, etc. Note that this is a Streamlit-specific method whose application here is **not** to replace a database or replace server-side storage, but to provide a temporary cache for the client-side app since Streamlit is stateless.
- **`_update_unread_count`**: helper method to update the unread message count in the Streamlit app via call/request to the server, updating the session state with the new count
- **`_show_login_or_signup_page`**: displays the login or signup page based on the user's current state (logged in or not).
[Other analogous pages for the app are similarly defined, such as `show_home_page`, `show_send_message_page`, `show_inbox_page`, `show_list_accounts_page`, `show_logout_page`, etc.]
- **`run_app`**: main entry point for the Streamlit app, running the app and displaying the appropriate page based on the user's current state and actions

Overall, the UI is designed to provide a real-time messaging experience with features like an unread message counter, dynamically updated inbox, and user authentication management. All pages are accessible at any time via the sidebar, and each session operates under a single logged-in user to ensure session integrity.

### Testing & Quality Assurance 
JoChat includes a comprehensive unit test suite, and has undergone integration testing. 

#### Running Tests  
To run any tests, first spin up a server with the ip and port specified in the test_base files.
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

Happy messaging on JoChat.
Dries and Jo.
```