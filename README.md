# DAD - Database Administration Dashboard

A web-based tool for deploying and managing database testing environments with various replication topologies.

## Features

- **MySQL Support**: Deploy MySQL, Percona, or MariaDB with async replication
- **Version Selection**: Choose specific database versions
- **Modern Terminology**: Uses source/replica instead of master/slave
- **Docker-based**: All environments run in Docker containers
- **Web UI**: Easy-to-use interface for environment management
- **Extensible**: Designed to support PostgreSQL and MongoDB in the future

## Architecture

- **Backend**: Python Flask API for Docker orchestration
- **Frontend**: HTML/CSS/JavaScript web interface
- **Docker Templates**: Reusable Docker Compose templates for different database types

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python backend/app.py
   ```

3. Open your browser to `http://localhost:5000`

## Project Structure

```
dad/
├── backend/          # Flask API server
├── frontend/         # Web UI files
├── docker_templates/ # Docker Compose templates
│   ├── mysql/
│   ├── percona/
│   └── mariadb/
├── static/           # Static assets
└── templates/        # HTML templates
```

## Future Features

- Galera replication support
- InnoDB Cluster support
- PostgreSQL support
- MongoDB support

