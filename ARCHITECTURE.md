# DAD Architecture

## Overview

DAD (Database Administration Dashboard) is designed with extensibility in mind. The architecture allows for easy addition of new database types (PostgreSQL, MongoDB) and replication topologies (Galera, InnoDB Cluster).

## Project Structure

```
dad/
├── backend/
│   └── app.py              # Flask API server
├── frontend/                # (Reserved for future React/Vue frontend)
├── docker_templates/        # Docker Compose templates
│   ├── mysql/
│   ├── percona/
│   ├── mariadb/
│   ├── postgresql/          # (Future)
│   └── mongodb/             # (Future)
├── static/                  # Static assets (CSS, JS)
├── templates/               # HTML templates
├── environments/            # Runtime environment data
└── requirements.txt         # Python dependencies
```

## Core Components

### 1. Backend API (`backend/app.py`)

The Flask application provides RESTful API endpoints:

- `GET /` - Web UI
- `GET /api/environments` - List all environments
- `POST /api/environments` - Create new environment
- `GET /api/environments/<id>` - Get environment details
- `DELETE /api/environments/<id>` - Delete environment
- `GET /api/health` - Health check

### 2. DatabaseManager Class

The `DatabaseManager` class handles all database environment operations:

- **Environment Management**: Create, list, delete environments
- **Docker Orchestration**: Generate and execute Docker Compose files
- **Template System**: Load and customize Docker Compose templates
- **Status Tracking**: Monitor environment status

### 3. Docker Templates

Docker Compose templates are stored in `docker_templates/<db_type>/<replication_type>_replication.yml`.

Templates use placeholders:
- `${DB_VERSION}` - Database version
- `${ENV_ID}` - Environment ID

## Extending DAD

### Adding a New Database Type (e.g., PostgreSQL)

1. **Create Template Directory**:
   ```bash
   mkdir -p docker_templates/postgresql
   ```

2. **Create Replication Template**:
   Create `docker_templates/postgresql/async_replication.yml`:
   ```yaml
   version: '3.8'
   services:
     source:
       image: postgres:${DB_VERSION}
       # ... configuration
   ```

3. **Update Backend**:
   In `backend/app.py`, update:
   - `create_environment()` - Add validation for new db_type
   - `_generate_default_async_template()` - Add image mapping
   - `_get_replication_command()` - Add PostgreSQL-specific commands
   - `_create_init_scripts()` - Add PostgreSQL initialization SQL

4. **Update Frontend**:
   In `templates/index.html`, add option to `<select id="db_type">`:
   ```html
   <option value="postgresql">PostgreSQL</option>
   ```

### Adding a New Replication Topology (e.g., Galera)

1. **Create Template**:
   Create `docker_templates/mysql/galera_replication.yml`

2. **Update Backend**:
   - Add validation in `create_environment()`
   - Update `generate_compose_file()` to handle new topology
   - Add topology-specific initialization logic

3. **Update Frontend**:
   Add option to replication type selector:
   ```html
   <option value="galera">Galera Cluster</option>
   ```

### Adding InnoDB Cluster Support

1. **Create Template**:
   Create `docker_templates/mysql/innodb_cluster.yml` with:
   - MySQL Router
   - Multiple MySQL instances
   - Group Replication configuration

2. **Update Backend**:
   - Add InnoDB Cluster initialization logic
   - Handle cluster bootstrap and member addition
   - Update status tracking for cluster health

## Docker Integration

### Sudo Password Handling

The system uses sudo for Docker commands. The password is configured in `backend/app.py`:
```python
SUDO_PASSWORD = "Yunus@7866"
```

**Security Note**: In production, move this to environment variables or a secure configuration file.

### Command Execution

Docker commands are executed via `run_docker_command()`:
```python
result = self.run_docker_command(
    f'docker-compose -f {compose_path} up -d',
    cwd=env_dir
)
```

## Environment Lifecycle

1. **Creation**:
   - Generate environment ID
   - Create environment directory
   - Generate Docker Compose file from template
   - Create initialization scripts
   - Start Docker containers
   - Save environment metadata

2. **Runtime**:
   - Environment metadata stored in `environments/<env_id>.json`
   - Docker containers managed via Docker Compose
   - Status tracked in metadata

3. **Deletion**:
   - Stop and remove containers (`docker-compose down -v`)
   - Remove environment directory
   - Delete metadata file

## Future Enhancements

### Planned Features

1. **Galera Replication**:
   - Multi-master replication
   - Cluster management
   - Node addition/removal

2. **InnoDB Cluster**:
   - MySQL Group Replication
   - MySQL Router integration
   - Cluster health monitoring

3. **PostgreSQL Support**:
   - Streaming replication
   - Logical replication
   - pgBouncer integration

4. **MongoDB Support**:
   - Replica sets
   - Sharded clusters
   - MongoDB Atlas integration

5. **Advanced Features**:
   - Environment snapshots
   - Backup/restore
   - Performance monitoring
   - Query analysis
   - Connection pooling

## Security Considerations

1. **Sudo Password**: Move to environment variables
2. **Network Isolation**: Each environment uses isolated Docker networks
3. **Authentication**: Add authentication for web UI (future)
4. **Input Validation**: Validate all user inputs
5. **Resource Limits**: Add Docker resource limits to prevent resource exhaustion

## Testing

To test the system:

1. Start the application:
   ```bash
   ./run.sh
   ```

2. Open browser to `http://localhost:5000`

3. Create a test environment:
   - Select MySQL
   - Enter version: `8.0`
   - Click "Create Environment"

4. Verify containers:
   ```bash
   sudo docker ps
   ```

5. Test connection:
   ```bash
   mysql -h 127.0.0.1 -P 3306 -u root -proot_password
   ```

## Troubleshooting

### Containers Not Starting

1. Check Docker logs:
   ```bash
   sudo docker-compose -f environments/<env_id>/docker-compose.yml logs
   ```

2. Verify Docker is running:
   ```bash
   sudo docker ps
   ```

3. Check disk space:
   ```bash
   df -h
   ```

### Permission Issues

1. Verify sudo password is correct
2. Check Docker group membership:
   ```bash
   groups
   ```

### Port Conflicts

If ports 3306 or 3307 are in use, modify the Docker Compose template to use different ports.

