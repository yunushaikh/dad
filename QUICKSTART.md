# DAD Quick Start Guide

## Prerequisites

- Python 3.7+
- Docker and Docker Compose
- Sudo access (for Docker commands)

## Installation

1. **Clone or navigate to the project**:
   ```bash
   cd /home/yunus/Projects/dad
   ```

2. **Run the setup script**:
   ```bash
   ./run.sh
   ```

   This will:
   - Create a Python virtual environment
   - Install dependencies
   - Start the Flask server

3. **Access the web UI**:
   Open your browser to `http://localhost:5000`

## Creating Your First Environment

1. Click **"+ Create Environment"** button

2. Fill in the form:
   - **Environment Name** (optional): e.g., `my-test-env`
   - **Database Type**: Select MySQL, Percona, or MariaDB
   - **Database Version**: Enter version tag (e.g., `8.0`, `8.2`, `5.7`)
   - **Replication Type**: Currently supports "Async Replication"

3. Click **"Create Environment"**

4. Wait for the environment to be created (this may take a few minutes as Docker images are downloaded)

## Connecting to Your Database

Once the environment is running, you can connect using:

**Source (Master)**:
```bash
mysql -h 127.0.0.1 -P 3306 -u root -proot_password
```

**Replica (Slave)**:
```bash
mysql -h 127.0.0.1 -P 3307 -u root -proot_password
```

### Connection Details

- **Root Password**: `root_password`
- **Replication User**: `repl`
- **Replication Password**: `repl_password`

## Managing Environments

### View All Environments

The main page displays all created environments with their status:
- 🟢 **Running**: Environment is active
- 🟡 **Stopped**: Environment is stopped
- 🔴 **Error**: Environment creation failed
- 🔵 **Creating**: Environment is being set up

### View Environment Details

Click **"👁️ View Details"** on any environment card to see:
- Environment ID
- Database type and version
- Replication configuration
- Container names
- Connection information

### Delete Environment

Click **"🗑️ Delete"** on any environment card to remove it. This will:
- Stop all containers
- Remove volumes
- Delete the environment directory

## Git Setup

To set up version control:

1. **Run the git setup helper**:
   ```bash
   ./setup_git.sh
   ```

2. **Follow the prompts** to configure:
   - Git username and email
   - Remote repository (optional)

3. **Make your first commit**:
   ```bash
   git add .
   git commit -m "Initial commit"
   git push -u origin master
   ```

## Troubleshooting

### Port Already in Use

If you see errors about ports 3306 or 3307 being in use:
- Stop existing MySQL instances
- Or modify the Docker Compose templates to use different ports

### Docker Permission Issues

If you encounter permission errors:
- Verify sudo password is correct in `backend/app.py`
- Check that Docker is installed and running:
  ```bash
  sudo docker ps
  ```

### Environment Creation Fails

1. Check Docker logs:
   ```bash
   sudo docker-compose -f environments/<env_id>/docker-compose.yml logs
   ```

2. Verify Docker images are available:
   ```bash
   sudo docker images | grep mysql
   ```

3. Check disk space:
   ```bash
   df -h
   ```

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand how to extend DAD
- Add support for PostgreSQL or MongoDB
- Implement Galera or InnoDB Cluster replication
- Customize Docker templates for your needs

## Support

For issues or questions, check the logs in the Flask console or Docker container logs.

