.PHONY: install run-server run-client run-all clean

# Default arguments (can be overridden)
SERVER_ARGS ?=
CLIENT_ARGS ?=

# Install dependencies
install:
	pip install -r server/requirements.txt
	pip install -r client/requirements.txt

# Start the server with optional arguments
run-server:
	cd server && python server.py $(SERVER_ARGS)

# Start the client with Streamlit, passing arguments correctly
run-client:
	cd client && streamlit run client.py -- $(CLIENT_ARGS)

# Start both server and client (server in the background)
run-all:
	cd server && python server.py $(SERVER_ARGS) & \
	sleep 2 && \
	cd client && streamlit run client.py -- $(CLIENT_ARGS)

# Clean up virtual environments or unnecessary files
clean:
	rm -rf server/venv client/venv
