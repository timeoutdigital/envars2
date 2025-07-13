# Use the official Python image based on .python-version.
FROM python:3.10-slim

# Install uv for package management.
RUN pip install uv

# Set the working directory inside the container.
WORKDIR /app

# Copy the rest of the application source code.
COPY . .

COPY dummy_gcp_credentials.json /app/dummy_gcp_credentials.json
ENV GOOGLE_APPLICATION_CREDENTIALS="/app/dummy_gcp_credentials.json"

ENV AWS_DEFAULT_REGION=eu-west-1
ENV AWS_REGION=eu-west-1

# Set the default command to run pytest using uv.
CMD ["uv", "run", "pytest", "-k", "gcp"]
