import grpc
import chat_service_pb2
import chat_service_pb2_grpc

# Setup connection
channel = grpc.insecure_channel("127.0.0.1:50051")
stub = chat_service_pb2_grpc.ChatServiceStub(channel)

# Sample credentials
username = "alice"
password = "secure123"  # Already hashed on the client-side

# Signup Request
print("Signing up...")
signup_response = stub.Signup(chat_service_pb2.SignupRequest(username=username, password=password))
print("Signup Response:", signup_response.status, signup_response.msg)

# Login Request
print("\nLogging in...")
login_response = stub.Login(chat_service_pb2.LoginRequest(username=username, password=password))
auth_token = login_response.auth_token  # Store this for future requests
print("Login Response:", login_response.status, login_response.msg, "Auth Token:", auth_token)

# Logout Request
if auth_token:
    print("\nLogging out...")
    logout_response = stub.Logout(chat_service_pb2.LogoutRequest(auth_token=auth_token))
    print("Logout Response:", logout_response.status, logout_response.msg)
