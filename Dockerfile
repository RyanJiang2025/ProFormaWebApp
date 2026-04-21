# Use a lightweight official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependency list first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your project files into the image
COPY . .

# Expose the port Streamlit will run on
EXPOSE 50053

# Run the Streamlit UI
CMD ["streamlit", "run", "main.py", "--server.address", "0.0.0.0", "--server.port", "50053"]
