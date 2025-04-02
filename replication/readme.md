  ## JoChat  
  JoChat is a distributed messaging system that supports user authentication, message delivery, and account management.

  This version of JoChat works with gRPC, so no longer a need to specify a messaging protocol.

  ## Quick Example Flow & Deployment  
  To set up and run JoChat, follow these steps in a **fresh virtual environment** (for the love of that which is holy):


#### 🧪 Example Flow

1. Start up a few servers, ideally waiting until you see the logs recognizing the leader:
   ```bash
   make run-server SERVER_ARGS="--server_id 1 --port 5001 --db_file=test_suite_server/test_chat1.db"
   make run-server SERVER_ARGS="--server_id 2 --port 5002 --db_file=test_suite_server/test_chat2.db --peers 1:127.0.0.1:5001"
   make run-server SERVER_ARGS="--server_id 3 --port 5003 --db_file=test_suite_server/test_chat3.db --peers 1:127.0.0.1:5001,2:127.0.0.1:5002"
2. Start a client:
   ```bash
   make run-client CLIENT_ARGS="--servers 127.0.0.1:5001,127.0.0.1:5002,127.0.0.1:5003"
3. Kill the leader (control c in the respective terminals)
   - The followers will detect the failure and hold an election. The client will detect the new leader via retry and keep working without any user intervention.




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
  │   │── chat1.db                      # SQLite database for storing users and messages in server 1 (process 1)
  │   │── chat2.db                      # SQLite database for storing users and messages in server 2 (process 2)
  │   │── test_suite_server/           # Test suite for server-side functionality
  │   │── test_int_grpc_sizes.py       # Integration test for gRPC message sizes
  │── Makefile                        # Automation for running server, client, and tests
  │── readme.md                       # Project documentation
  │── requirements.txt                 # Dependencies required for the project
  ```

  ## Code Documentation

  ### The Cluster
- **Decentralized Peer-to-Peer Servers**
Each server starts independently and is given a list of peers via command-line arguments. When a new server joins, it queries the leader, which at the least must be provided as a peer to discover the current leader and synchronizes its state by requesting a full database snapshot via the AddReplica RPC, it also receives all peers active in the cluster visible to the leader.

- **Leader Election (Lowest-ID Wins)**
Servers monitor **heartbeats** from the leader. If no heartbeat is received within a timeout window (LEADER_TIMEOUT_SECS), an election is triggered. The server with the **lowest ID among reachable peers** becomes the new leader. Each node does this process independently, and agrees on the new leader among them. A small ping is sent by a node to see who is reachable at election time.

- **Replication**
When the leader handles a write (e.g., sign-up, send message, logout), it propagates that action to all followers using gRPC Replicate calls. These operations are encoded as typed replication requests and include payloads like message contents or session tokens.

- **Snapshot-Based Rejoin**
New replicas receive a full snapshot of the leader’s database on join — including users, messages, and sessions — and then are added to the leader’s peer list, becoming full cluster members. This allows for any new node to join the cluster, and is also how we start up the first three servers.

- **Client-Side Failover Logic**
The ChatServerClient class in client.py manages a list of server addresses. It automatically detects when a server is unreachable or refuses writes due to not being the leader, and transparently retries requests on the next server in the list. It can also call ClusterInfo to refresh its view of the current cluster. It polls and does this within a timeout window (10 seconds by default). Implemented as its own class so that the client itself and the user itself does not have to do anything to do with the switch but can just naively call RPC requests. The ChatServerClient handles the connection with the Cluster.


### The Server
The server is the **backbone** of JoChat.

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
- **Cluster Tests (`test_suite_server/`)**
  - Persistence of messages when killing random servers and starting them back up.
  - Replication: Starting up servers and mimicking traffic and checking the storage of the other servers.
  - Failover: Killing a server that has had a lot of traffic and making sure the user seamlesly can use another node in the cluster.

Happy messaging on JoChat.
Dries and Jo.
```