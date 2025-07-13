# Running Envars2 with Docker

This document provides guidance on how to integrate `envars2` into a containerized application running on a cloud instance (e.g., EC2 or a VM).

There are three common approaches to this, each with its own trade-offs:

## Approach 1: The "Entrypoint" Method (Recommended)

This is the most common and recommended approach. It involves using the `envars2 exec` command as the entrypoint for your container.

### How it Works

1.  **Package `envars.yml` with your Application:** The `envars.yml` file is included in your application's source code and is copied into the Docker image during the build process.

2.  **Install `envars2` in the Docker Image:** Your `Dockerfile` will include a step to install the `envars2` tool.

3.  **Set the `ENTRYPOINT`:** The `ENTRYPOINT` of your `Dockerfile` is set to use `envars2 exec`.

Here's an example of what the `Dockerfile` might look like:

```dockerfile
FROM python:3.10-slim

# Install uv
RUN pip install uv

# Copy your application code
WORKDIR /app
COPY . .

# Install dependencies, including envars2
RUN uv sync --all-extras

# Set the entrypoint to use envars2
ENTRYPOINT ["envars2", "exec", "--env", "$ENVARS_ENV", "--loc", "$LOCATION", "--"]

# The command to run your application
CMD ["python", "my_app.py"]
```

### How to Use It

When you run the Docker container, you would pass the `ENVARS_ENV` and `LOCATION` as environment variables:

```bash
docker run -e ENVARS_ENV=prod -e LOCATION=aws my-app-image
```

### Advantages

*   **Simple and Clean:** This approach is very clean and easy to understand. The `Dockerfile` clearly shows how the environment is being set up.
*   **Secure:** Secrets are only decrypted at runtime, inside the container. They are never stored in plaintext on the host machine or in an intermediate file.
*   **Portable:** The Docker image is self-contained and can be run in any environment, as long as the `ENVARS_ENV` and `LOCATION` environment variables are provided.

## Approach 2: The "Env-File" Method with Process Substitution (Recommended for Host-Based Execution)

This approach involves running `envars2` on the host machine (the EC2 instance or VM) and passing the environment variables to the Docker container at runtime, without writing them to disk. This is the most secure way to handle this scenario.

### How it Works

1.  **Install `envars2` on the Host:** The `envars2` tool is installed on the host machine.

2.  **Use Process Substitution:** You use the `<()` syntax (supported by `bash` and `zsh`) to treat the output of the `envars2 print` command as a file.

### Example

```bash
docker run --env-file <(envars2 print --env prod --loc aws) my-app-image
```

### Advantages

*   **Highly Secure:** The environment variables, including any decrypted secrets, are never written to the disk. They are passed directly from the `envars2` process to the `docker` process through an in-memory pipe.
*   **Simple and Flexible:** This approach is a single, clean command and allows you to easily generate different environment configurations without rebuilding your Docker image.

### Disadvantages

*   **Requires `envars2` on the Host:** This approach requires you to install and manage `envars2` on the host machine.
*   **Shell Dependent:** Process substitution is not available in all shells (e.g., it's not supported in `sh`).

## Approach 3: The "Sidecar" Method (for Container Orchestrators)

In this approach, you use a separate "sidecar" container to fetch the environment variables and make them available to your application container. This is a common pattern in container orchestration systems like Kubernetes.

### How it Works

1.  **The "Init Container":** You would have an "init container" that runs `envars2 yaml` to fetch the environment variables and write them to a shared volume.

2.  **The Application Container:** Your application container would then source the environment variables from the shared volume.

### Example (Kubernetes Pod)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  initContainers:
  - name: envars-init
    image: my-envars-image
    command: ["/bin/sh", "-c"]
    args:
    - "envars2 yaml --env prod --loc aws > /etc/envars/envars.env"
    volumeMounts:
    - name: envars-volume
      mountPath: /etc/envars
  containers:
  - name: my-app
    image: my-app-image
    command: ["/bin/sh", "-c"]
    args:
    - "source /etc/envars/envars.env && python my_app.py"
    volumeMounts:
    - name: envars-volume
      mountPath: /etc/envars
  volumes:
  - name: envars-volume
    emptyDir: {}
```

### Advantages

*   **Separation of Concerns:** This approach cleanly separates the concern of fetching secrets from the application's logic.
*   **Reusable:** The `envars-init` container can be reused across multiple applications.

### Disadvantages

*   **More Complex:** This approach is more complex to set up and manage, especially if you are not already using a container orchestration system.
*   **Less Secure:** The environment variables are written to a file on a shared volume, which could be a security risk if not properly secured.

## Conclusion

For most use cases, the **"Entrypoint" method** is the recommended approach. It is simpler, more secure, and easier to manage. The **"Env-File" method with process substitution** is an excellent and highly secure alternative if you are running `envars2` on the host. The "Sidecar" method is a good option for more complex scenarios where you need to share the same set of environment variables across multiple containers in a pod.

In all cases, the key is to ensure that the instance (EC2 or VM) has the necessary IAM role and permissions to access the KMS key and any remote secrets (from Parameter Store or Secret Manager).
