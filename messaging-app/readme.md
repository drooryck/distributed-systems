## JoChat  
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
│── test_suite/             # Directory containing all unit tests
│   │── test_1_login.py     # Test for user login functionality
│   │── test_2_signup.py    # Test for user signup functionality
│   │── … (other test cases)
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
```

## 📖 Code Documentation & System Overview  

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
- Implements a **request-response model**, where clients send JSON requests (e.g., `"send_message"`, `"fetch_messages"`, `"delete_account"`), and the server responds with data or status updates.
- The server processes actions using a **queue per client**, polling actions in sequence.
- **Concurrency control:** Implements a **coarse-grained locking mechanism**, allowing multiple clients to be handled simultaneously without conflicts.

### 💻 The Client (Frontend)
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

#### 🔑 Security & Performance
- **Uses a 4-byte big-endian length prefix** to ensure message boundaries are correctly interpreted.  
- **Maintains a persistent socket connection** within **Streamlit’s session state**, reducing reconnections and improving performance.  
- Implements **automatic message retrieval**:
  - **`send_messages_to_client`** → Fetches new messages marked for immediate delivery.  
  - **`fetch_away_msgs`** → Fetches older undelivered messages manually.  
- **Security:** Passwords are **hashed using SHA-256** before transmission.  

#### 🌐 Client UI (Streamlit)
- **Real-time messaging experience** with:
  - **Unread message counter**
  - **Dynamically updated inbox**
  - **User authentication management**
- Each session operates under **a single logged-in user**, ensuring session integrity.