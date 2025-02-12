JoChat is a distributed messaging system that supports user authentication, message delivery, and account management.

0. Quick set-up, Deployment Documentation
1. 
You will need to run the following commands in a fresh virtual environment.
- pip install -r requirements.txt
- make run-server (optional cmd-line arguments --host 0.0.0.0 --port 5000 --protocol json/binary)
- make run-client
This will spin up a streamlit application in your web-browser from which you will be able to use the messaging app. You can sign up, log-in, see the number of unread messages while you were away, send a message to another user, list all accounts that match a wildcard pattern and paginate through them, delete the account of the user you are logged in as, and log out of the account you are currently signed in with. 

1. Here is an overview of all files,
messaging-app/
│── test_suite/             # Directory containing all unit tests
│   │── test_1_login.py     # Test for user login functionality
│   │── test_2_signup.py    # Test for user signup functionality
│   │── ... (other test cases)
│   │── test_base.py        # Base test class
│   │── test_suite.py       # Runs all tests together
│── chat.db                 # SQLite database for storing users and messages
│── client.py               # Client-side script to interact with the server
│── server.py               # Main server implementation
│── Makefile                # Automation for running server, client, and tests
│── requirements.txt        # Dependencies required for the project
│── readme.txt              # Basic project documentation
│── test_log.txt            # Logs for test results
│── client_log.txt          # Logs for client interactions
│── streamlit_app2.py       # Streamlit application (if applicable)

1. Explanations of files in a more 'literate programming' style. Code Documentation.

The server is the backbone of the messaging system. It listens for client connections, processes user requests, and manages message delivery. It operates using socket programming, allowing multiple clients to communicate with it over a network. The server handles user authentication, allowing users to sign up, log in, and log out while ensuring that only one socket is logged in to any one account, and any one account is only present on one socket.
Messages are stored in an SQLite database (chat.db), which keeps track of registered users and all sent messages. Each message includes metadata such as the sender, recipient, content, and delivery status. If a recipient is offline when a message is sent, the server flags it as "sent while away", ensuring that it is available when the user logs back in.
A threading model is used to handle multiple clients simultaneously. When a client connects, the server spawns a new thread to manage communication with that specific client. The server follows a request-response model, where clients send JSON-formatted requests specifying an action (e.g., "send_message", "fetch_messages", "delete_account"), and the server responds with the corresponding data or status message. The server spins up a queue of actions for each client that the server polls through.
The server uses a coarse-grained locking mechanism on the level of processing a client action, so that actions from multiple clients can be handled concurrently.

The client is responsible for maintaining a persistent connection with the server using TCP sockets and exchanging length-prefixed JSON messages for structured communication. It follows a request-response model, where each request consists of a DJSON object containing a "msg_type" field (specifying the action, e.g., "login", "send_message") and a "data" field containing relevant parameters. Messages are sent using a 4-byte big-endian length prefix, ensuring that the server correctly interprets message boundaries. The client maintains a persistent socket connection within Streamlit’s session state to avoid frequent reconnections and improve performance. It implements automatic message retrieval by periodically calling "send_messages_to_client" to fetch new messages marked for immediate delivery, while older undelivered messages must be fetched manually using "fetch_away_msgs". For security, passwords are hashed using SHA-256 before being transmitted. The client UI, built with Streamlit, dynamically updates unread message counts and inbox contents, providing a real-time messaging experience. It also manages user authentication, ensuring that each session only operates under a single logged-in user.