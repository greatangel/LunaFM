# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY ./LunaFM_version0.3_linux.py .
COPY ./requirements.txt .

# Install any needed dependencies specified in requirements.txt
RUN apt-get update && apt-get install -y ffmpeg
RUN pip install --no-cache-dir -r requirements.txt

# Command to run the application
CMD ["python", "LunaFM_version0.3.py"]