.PHONY: install run-server run-client run-all clean

# Install dependencies
install:
	pip install -r requirements.txt

# Start the server
run-server:
	python server.py

# Start the client with Streamlit
run-client:
	streamlit run client.py

# Start both server and client (server in the background)
run-all:
	python server.py & \
	sleep 2 && \
	streamlit run client.py

# Clean up virtual environment (if used)
clean:
	rm -rf venv
