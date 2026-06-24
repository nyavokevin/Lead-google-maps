import lmstudio as lms

# Connect to the local LM Studio instance and pick a loaded model
# Replace with the exact identifier of your downloaded model (e.g., "llama-3-8b")
model = lms.llm("google/gemma-4-e4b")

# Initialize a chat context
chat = lms.Chat("You are a helpful and concise AI assistant.")
chat.add_user_message("Why is the sky blue?")

# Generate a response and print it
response = model.respond(chat)
print(response)