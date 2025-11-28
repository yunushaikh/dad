#!/usr/bin/env python3
"""
DAD - Database Administration Dashboard
Backend Flask API for managing database testing environments
"""

import os
import json
import subprocess
import yaml
import socket
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')
CORS(app)

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DOCKER_TEMPLATES_DIR = PROJECT_ROOT / 'docker_templates'
ENVIRONMENTS_DIR = PROJECT_ROOT / 'environments'
SUDO_PASSWORD = "Yunus@7866"

# Ensure directories exist
ENVIRONMENTS_DIR.mkdir(exist_ok=True)


class DatabaseManager:
    """Manages database environments using Docker"""
    
    def __init__(self):
        self.environments = {}
        self.load_environments()
    
    def load_environments(self):
        """Load existing environments from disk"""
        if ENVIRONMENTS_DIR.exists():
            for env_file in ENVIRONMENTS_DIR.glob('*.json'):
                with open(env_file, 'r') as f:
                    env_data = json.load(f)
                    self.environments[env_data['id']] = env_data
    
    def save_environment(self, env_data):
        """Save environment metadata to disk"""
        env_file = ENVIRONMENTS_DIR / f"{env_data['id']}.json"
        with open(env_file, 'w') as f:
            json.dump(env_data, f, indent=2)
    
    def delete_environment_file(self, env_id):
        """Delete environment metadata file"""
        env_file = ENVIRONMENTS_DIR / f"{env_id}.json"
        if env_file.exists():
            env_file.unlink()
    
    def find_free_ports(self, count, start_port=10001):
        """Find free ports starting from start_port"""
        free_ports = []
        current_port = start_port
        
        # Get all ports currently in use by existing environments
        used_ports = set()
        for env_id, env_data in self.environments.items():
            if 'ports' in env_data:
                for port_info in env_data['ports'].values():
                    if isinstance(port_info, dict) and 'host' in port_info:
                        used_ports.add(port_info['host'])
        
        # Check all Docker containers for port usage
        result = self.run_docker_command('docker ps --format "{{.Ports}}"')
        if result['success']:
            import re
            # Extract port numbers from docker ps output (format: 0.0.0.0:PORT->3306/tcp)
            port_matches = re.findall(r':(\d+)->', result['stdout'])
            for port in port_matches:
                try:
                    used_ports.add(int(port))
                except:
                    pass
        
        # Also check docker compose services
        for env_id, env_data in self.environments.items():
            env_dir = ENVIRONMENTS_DIR / env_id
            compose_path = env_dir / 'docker-compose.yml'
            if compose_path.exists():
                result = self.run_docker_command(
                    f'docker compose -f {compose_path} ps --format json',
                    cwd=env_dir
                )
                if result['success']:
                    try:
                        containers_output = result['stdout'].strip()
                        if containers_output:
                            for line in containers_output.split('\n'):
                                if line.strip():
                                    try:
                                        c = json.loads(line)
                                        if isinstance(c, dict) and 'Ports' in c:
                                            ports_str = c.get('Ports', '')
                                            port_matches = re.findall(r':(\d+)->', ports_str)
                                            for port in port_matches:
                                                try:
                                                    used_ports.add(int(port))
                                                except:
                                                    pass
                                    except:
                                        pass
                    except:
                        pass
        
        # Find free ports
        while len(free_ports) < count and current_port < 65535:
            # Check if port is in use by system
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex(('127.0.0.1', current_port))
                sock.close()
                
                # Port is free if connection fails (result != 0) and not in used_ports
                if result != 0 and current_port not in used_ports:
                    free_ports.append(current_port)
            except:
                pass
            current_port += 1
        
        if len(free_ports) < count:
            raise Exception(f"Could not find {count} free ports starting from {start_port}")
        
        return free_ports
    
    def run_docker_command(self, command, cwd=None):
        """Run Docker command with sudo"""
        full_command = f'echo "{SUDO_PASSWORD}" | sudo -S {command}'
        try:
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=300
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Command timed out',
                'returncode': -1
            }
        except Exception as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def create_environment(self, db_type, db_version, replication_type='async', name=None, replica_count=1):
        """Create a new database environment"""
        env_id = f"{db_type}_{db_version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if name:
            env_id = f"{name}_{env_id}"
        
        env_data = {
            'id': env_id,
            'db_type': db_type,
            'db_version': db_version,
            'replication_type': replication_type,
            'replica_count': replica_count,
            'name': name or env_id,
            'status': 'creating',
            'created_at': datetime.now().isoformat(),
            'containers': []
        }
        
        # Generate Docker Compose file
        compose_file = self.generate_compose_file(env_data)
        
        # Save environment metadata
        self.save_environment(env_data)
        self.environments[env_id] = env_data
        
        # Start the environment
        env_dir = ENVIRONMENTS_DIR / env_id
        env_dir.mkdir(exist_ok=True)
        
        compose_path = env_dir / 'docker-compose.yml'
        with open(compose_path, 'w') as f:
            yaml.dump(compose_file, f, default_flow_style=False)
        
        # Create initialization SQL scripts
        self._create_init_scripts(env_dir, env_data)
        
        # Start containers
        result = self.run_docker_command(
            f'docker compose -f {compose_path} up -d',
            cwd=env_dir
        )
        
        if result['success']:
            # Wait for containers to be ready
            import time
            print("Waiting for containers to initialize...")
            time.sleep(10)  # Give containers more time to initialize
            
            # Get container status first (including created but not started)
            containers_result = self.run_docker_command(
                f'docker compose -f {compose_path} ps -a --format json',
                cwd=env_dir
            )
            
            container_info = []
            if containers_result['success']:
                try:
                    containers_output = containers_result['stdout'].strip()
                    if not containers_output:
                        env_data['status'] = 'error'
                        env_data['error'] = 'No containers found after creation'
                        self.save_environment(env_data)
                        return env_data, result
                    
                    # Handle both single object and array responses, or newline-separated
                    containers = []
                    for line in containers_output.split('\n'):
                        if line.strip():
                            try:
                                containers.append(json.loads(line))
                            except:
                                pass
                    
                    if not containers:
                        # Try parsing as single JSON object
                        try:
                            containers = [json.loads(containers_output)]
                        except:
                            pass
                    
                    for c in containers:
                        if isinstance(c, dict):
                            container_name = c.get('Name', '')
                            container_state = c.get('State', 'unknown')
                            container_info.append({
                                'name': container_name,
                                'state': container_state
                            })
                            
                            # Check if any containers failed or are created but not started
                            if container_state in ['exited', 'dead', 'created']:
                                # Get container logs for debugging
                                log_result = self.run_docker_command(
                                    f'docker logs {container_name} --tail 50 2>&1',
                                    cwd=env_dir
                                )
                                if log_result['success']:
                                    env_data['container_logs'] = env_data.get('container_logs', {})
                                    env_data['container_logs'][container_name] = log_result['stdout'][-500:]  # Last 500 chars
                    
                    # Update containers list
                    env_data['containers'] = [c.get('name') for c in container_info]
                except Exception as e:
                    print(f"Error parsing container status: {e}")
                    print(f"Container output: {containers_result['stdout']}")
            
            # Determine overall status
            if container_info:
                running_count = sum(1 for c in container_info if c.get('state') == 'running')
                if running_count == len(container_info):
                    env_data['status'] = 'running'
                    # Configure replication only if all containers are running
                    print("Configuring replication...")
                    self._configure_replication(env_dir, env_data)
                elif running_count > 0:
                    env_data['status'] = 'partial'
                    env_data['error'] = f'Some containers are not running. Running: {running_count}/{len(container_info)}'
                else:
                    env_data['status'] = 'error'
                    env_data['error'] = 'All containers failed to start. Check container logs.'
            else:
                env_data['status'] = 'error'
                env_data['error'] = 'No containers found'
        else:
            # Check if error is due to port conflict
            if 'address already in use' in result['stderr'].lower() or 'port' in result['stderr'].lower():
                env_data['error'] = f"Port conflict detected. {result['stderr'][:200]}. Port 3306 may be in use by another service."
            else:
                env_data['error'] = result['stderr']
            env_data['status'] = 'error'
        
        self.save_environment(env_data)
        return env_data, result
    
    def generate_compose_file(self, env_data):
        """Generate Docker Compose file based on environment configuration"""
        db_type = env_data['db_type'].lower()
        version = env_data['db_version']
        replication_type = env_data['replication_type']
        replica_count = env_data.get('replica_count', 1)
        
        # Find free ports for this environment
        total_containers = 1 + replica_count  # source + replicas
        try:
            free_ports = self.find_free_ports(total_containers, start_port=10001)
            env_data['ports'] = {
                'source': {'host': free_ports[0], 'container': 3306},
            }
            for i in range(1, replica_count + 1):
                env_data['ports'][f'replica{i}'] = {
                    'host': free_ports[i],
                    'container': 3306
                }
        except Exception as e:
            print(f"Error finding free ports: {e}")
            # Fallback to sequential ports
            free_ports = list(range(10001, 10001 + total_containers))
            env_data['ports'] = {
                'source': {'host': free_ports[0], 'container': 3306},
            }
            for i in range(1, replica_count + 1):
                env_data['ports'][f'replica{i}'] = {
                    'host': free_ports[i],
                    'container': 3306
                }
        
        # Generate compose file with multiple replicas
        compose_data = self._generate_async_template_with_replicas(
            db_type, version, replica_count, env_data['id'], env_data['ports']
        )
        
        return compose_data
    
    def _generate_async_template_with_replicas(self, db_type, version, replica_count, env_id, ports_config):
        """Generate async replication template with multiple replicas"""
        # Determine image based on db_type
        image_map = {
            'mysql': f'mysql:{version}',
            'percona': f'percona/percona-server:{version}',
            'mariadb': f'mariadb:{version}'
        }
        
        image = image_map.get(db_type.lower(), f'mysql:{version}')
        root_password = 'root_password'
        
        # Get source port
        source_port = ports_config['source']['host']
        
        services = {
            'source': {
                'image': image,
                'container_name': f'{env_id}_source',
                'environment': {
                    'MYSQL_ROOT_PASSWORD': root_password,
                },
                'ports': [f'{source_port}:3306'],
                'volumes': [
                    'source_data:/var/lib/mysql',
                    './init_source.sql:/docker-entrypoint-initdb.d/init.sql'
                ],
                'command': self._get_replication_command(db_type, 'source'),
                'networks': ['db_network'],
                'healthcheck': {
                    'test': ['CMD', 'mysqladmin', 'ping', '-h', 'localhost', '-uroot', f'-p{root_password}'],
                    'interval': '10s',
                    'timeout': '5s',
                    'retries': 10
                }
            }
        }
        
        volumes = {'source_data': {}}
        depends_on = ['source']
        
        # Add replicas
        for i in range(1, replica_count + 1):
            replica_name = f'replica{i}'
            replica_port = ports_config[replica_name]['host']
            server_id = i + 1
            replica_cmd = self._get_replication_command(db_type, 'replica')
            replica_cmd.append(f'--server-id={server_id}')
            
            services[replica_name] = {
                'image': image,
                'container_name': f'{env_id}_{replica_name}',
                'depends_on': {
                    'source': {'condition': 'service_healthy'}
                },
                'environment': {
                    'MYSQL_ROOT_PASSWORD': root_password,
                },
                'ports': [f'{replica_port}:3306'],
                'volumes': [
                    f'{replica_name}_data:/var/lib/mysql',
                    f'./init_replica.sql:/docker-entrypoint-initdb.d/init.sql'
                ],
                'command': replica_cmd,
                'networks': ['db_network'],
                'healthcheck': {
                    'test': ['CMD', 'mysqladmin', 'ping', '-h', 'localhost', '-uroot', f'-p{root_password}'],
                    'interval': '10s',
                    'timeout': '5s',
                    'retries': 10
                }
            }
            volumes[f'{replica_name}_data'] = {}
        
        return {
            'version': '3.8',
            'services': services,
            'volumes': volumes,
            'networks': {
                'db_network': {
                    'driver': 'bridge'
                }
            }
        }
    
    def _get_replication_command(self, db_type, role):
        """Get replication command based on database type and role"""
        db_type_lower = db_type.lower()
        
        if db_type_lower in ['mysql', 'percona']:
            if role == 'source':
                return [
                    '--server-id=1',
                    '--log-bin=mysql-bin',
                    '--binlog-format=ROW',
                    '--gtid-mode=ON',
                    '--enforce-gtid-consistency=ON',
                    '--character-set-server=utf8mb4',
                    '--collation-server=utf8mb4_unicode_ci'
                ]
            else:
                # Server ID will be set dynamically based on replica number
                return [
                    '--log-bin=mysql-bin',
                    '--binlog-format=ROW',
                    '--gtid-mode=ON',
                    '--enforce-gtid-consistency=ON',
                    '--relay-log=replica-relay-bin',
                    '--read-only=1',
                    '--character-set-server=utf8mb4',
                    '--collation-server=utf8mb4_unicode_ci'
                ]
        elif db_type_lower == 'mariadb':
            if role == 'source':
                return [
                    '--server-id=1',
                    '--log-bin=mysql-bin',
                    '--binlog-format=ROW',
                    '--gtid-domain-id=1',
                    '--character-set-server=utf8mb4',
                    '--collation-server=utf8mb4_unicode_ci'
                ]
            else:
                return [
                    '--log-bin=mysql-bin',
                    '--binlog-format=ROW',
                    '--gtid-domain-id=1',
                    '--relay-log=replica-relay-bin',
                    '--read-only=1',
                    '--character-set-server=utf8mb4',
                    '--collation-server=utf8mb4_unicode_ci'
                ]
        return []
    
    def _create_init_scripts(self, env_dir, env_data):
        """Create SQL initialization scripts for replication setup"""
        db_type = env_data['db_type'].lower()
        
        # Source initialization script
        source_init = """-- Source initialization script
CREATE USER IF NOT EXISTS 'repl'@'%' IDENTIFIED BY 'repl_password';
GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';
FLUSH PRIVILEGES;
"""
        
        # Replica initialization script (minimal - replication will be configured later)
        replica_init = """-- Replica initialization script
-- Replication will be configured after source is ready
"""
        
        with open(env_dir / 'init_source.sql', 'w') as f:
            f.write(source_init)
        
        with open(env_dir / 'init_replica.sql', 'w') as f:
            f.write(replica_init)
    
    def _configure_replication(self, env_dir, env_data):
        """Configure replication after containers are running"""
        import time
        
        db_type = env_data['db_type'].lower()
        replica_count = env_data.get('replica_count', 1)
        source_container = f"{env_data['id']}_source"
        
        # Wait for source to be ready and replication user to exist
        max_retries = 60  # Increased retries
        source_ready = False
        for i in range(max_retries):
            # Check if MySQL is ready
            result = self.run_docker_command(
                f'docker exec {source_container} mysqladmin ping -h localhost -uroot -proot_password',
                cwd=env_dir
            )
            if result['success']:
                # Check if replication user exists (simplified query to avoid quote issues)
                user_check = self.run_docker_command(
                    f'docker exec {source_container} mysql -uroot -proot_password -e "SELECT COUNT(*) FROM mysql.user WHERE User=\'repl\'"',
                    cwd=env_dir
                )
                if user_check['success'] and ('1' in user_check['stdout'] or 'repl' in user_check['stdout']):
                    source_ready = True
                    break
            time.sleep(2)
        
        if not source_ready:
            print(f"Warning: Source {source_container} not ready for replication setup")
            return
        
        # Configure each replica
        for i in range(1, replica_count + 1):
            replica_name = f"replica{i}"
            replica_container = f"{env_data['id']}_{replica_name}"
            
            # Wait for replica to be ready
            replica_ready = False
            for j in range(max_retries):
                result = self.run_docker_command(
                    f'docker exec {replica_container} mysqladmin ping -h localhost -uroot -proot_password',
                    cwd=env_dir
                )
                if result['success']:
                    replica_ready = True
                    break
                time.sleep(2)
            
            if not replica_ready:
                print(f"Warning: Replica {replica_container} not ready")
                continue
            
            # Create SQL file for replication setup
            setup_sql_file = env_dir / f'setup_replica_{i}.sql'
            
            # Stop any existing replication first
            # Determine MySQL version to set appropriate public key option for caching_sha2_password
            db_version = env_data.get('db_version', '8.0')
            version_major = int(db_version.split('.')[0]) if db_version.split('.')[0].isdigit() else 8
            
            if db_type in ['mysql', 'percona']:
                if version_major >= 8:
                    # MySQL/Percona 8.0+ GTID replication with caching_sha2_password support
                    stop_cmd = "STOP REPLICA;"
                    change_master_sql = """CHANGE REPLICATION SOURCE TO
  SOURCE_HOST='source',
  SOURCE_USER='repl',
  SOURCE_PASSWORD='repl_password',
  SOURCE_AUTO_POSITION=1,
  GET_SOURCE_PUBLIC_KEY=1;"""
                    start_sql = "START REPLICA;"
                else:
                    # MySQL/Percona 5.7 GTID replication
                    stop_cmd = "STOP SLAVE;"
                    change_master_sql = """CHANGE MASTER TO
  MASTER_HOST='source',
  MASTER_USER='repl',
  MASTER_PASSWORD='repl_password',
  MASTER_AUTO_POSITION=1,
  GET_MASTER_PUBLIC_KEY=1;"""
                    start_sql = "START SLAVE;"
            else:
                # MariaDB GTID replication (doesn't use caching_sha2_password by default)
                stop_cmd = "STOP SLAVE;"
                change_master_sql = """CHANGE MASTER TO
  MASTER_HOST='source',
  MASTER_USER='repl',
  MASTER_PASSWORD='repl_password',
  MASTER_USE_GTID=slave_pos;"""
                start_sql = "START SLAVE;"
            
            # Write SQL commands to file
            with open(setup_sql_file, 'w') as f:
                f.write(f"{stop_cmd}\n")
                f.write(f"{change_master_sql}\n")
                f.write(f"{start_sql}\n")
            
            # Copy SQL file into container
            copy_cmd = f'docker cp {setup_sql_file} {replica_container}:/tmp/setup_replication.sql'
            copy_result = self.run_docker_command(copy_cmd, cwd=env_dir)
            
            if copy_result['success']:
                # Execute SQL file from inside container
                exec_cmd = f'docker exec {replica_container} sh -c "mysql -uroot -proot_password < /tmp/setup_replication.sql"'
                result = self.run_docker_command(exec_cmd, cwd=env_dir)
            else:
                # Fallback: Execute commands one by one
                print(f"Using fallback method for {replica_container}...")
                # Clean up the SQL command for single-line execution
                change_master_clean = change_master_sql.strip().replace('\n', ' ').replace('  ', ' ')
                commands = [stop_cmd, change_master_clean, start_sql]
                result = {'success': True, 'stderr': ''}
                
                for cmd in commands:
                    exec_cmd = f'docker exec {replica_container} mysql -uroot -proot_password -e "{cmd}"'
                    cmd_result = self.run_docker_command(exec_cmd, cwd=env_dir)
                    if not cmd_result['success']:
                        result = cmd_result
                        break
            
            if result['success']:
                print(f"✓ Replication configured successfully on {replica_container}")
                time.sleep(2)
                
                # Verify replication status
                if db_type in ['mysql', 'percona']:
                    status_cmd = "SHOW REPLICA STATUS\\G"
                else:
                    status_cmd = "SHOW SLAVE STATUS\\G"
                
                status_result = self.run_docker_command(
                    f'docker exec {replica_container} mysql -uroot -proot_password -e "{status_cmd}"',
                    cwd=env_dir
                )
                if status_result['success']:
                    # Check if replication is running
                    if 'Replica_IO_Running: Yes' in status_result['stdout'] or 'Slave_IO_Running: Yes' in status_result['stdout']:
                        print(f"✓ Replication is running on {replica_container}")
                    else:
                        print(f"⚠ Replication may not be running properly on {replica_container}")
            else:
                print(f"✗ Error configuring replication on {replica_container}: {result['stderr']}")
            
            # Clean up SQL file
            if setup_sql_file.exists():
                setup_sql_file.unlink()
    
    def delete_environment(self, env_id):
        """Delete a database environment"""
        if env_id not in self.environments:
            return {'success': False, 'error': 'Environment not found'}
        
        env_dir = ENVIRONMENTS_DIR / env_id
        compose_path = env_dir / 'docker-compose.yml'
        
        errors = []
        
        if compose_path.exists():
            # Stop and remove containers
            result = self.run_docker_command(
                f'docker compose -f {compose_path} down -v',
                cwd=env_dir
            )
            
            if not result['success']:
                errors.append(f"Failed to stop containers: {result['stderr']}")
        
        # Remove environment directory
        if env_dir.exists():
            try:
                import shutil
                shutil.rmtree(env_dir)
            except Exception as e:
                errors.append(f"Failed to remove directory: {str(e)}")
        
        # Remove from memory and disk
        if env_id in self.environments:
            del self.environments[env_id]
        self.delete_environment_file(env_id)
        
        if errors:
            return {'success': True, 'message': 'Environment deleted with warnings', 'warnings': errors}
        
        return {'success': True, 'message': 'Environment deleted successfully'}
    
    def list_environments(self):
        """List all environments"""
        # Update status for each environment
        for env_id, env_data in self.environments.items():
            env_dir = ENVIRONMENTS_DIR / env_id
            compose_path = env_dir / 'docker-compose.yml'
            
            if compose_path.exists():
                result = self.run_docker_command(
                    f'docker compose -f {compose_path} ps -a --format json',
                    cwd=env_dir
                )
                if result['success']:
                    try:
                        containers = json.loads(result['stdout'])
                        if not isinstance(containers, list):
                            containers = [containers] if containers else []
                        
                        container_info = []
                        for c in containers:
                            if isinstance(c, dict):
                                container_info.append({
                                    'name': c.get('Name', ''),
                                    'state': c.get('State', 'unknown')
                                })
                        
                        if container_info:
                            running = sum(1 for c in container_info if c.get('state') == 'running')
                            total = len(container_info)
                            
                            # Update containers list
                            env_data['containers'] = [c.get('name') for c in container_info]
                            
                            if running == total:
                                env_data['status'] = 'running'
                            elif running > 0:
                                env_data['status'] = 'partial'
                                env_data['error'] = f'Running: {running}/{total} containers'
                            else:
                                env_data['status'] = 'stopped'
                        else:
                            env_data['status'] = 'error'
                            env_data['error'] = 'No containers found'
                    except Exception as e:
                        print(f"Error updating status for {env_id}: {e}")
        
        return list(self.environments.values())
    
    def get_environment(self, env_id):
        """Get environment details"""
        if env_id not in self.environments:
            return None
        return self.environments[env_id]


# Initialize database manager
db_manager = DatabaseManager()


@app.route('/')
def index():
    """Serve the main UI"""
    return render_template('index.html')


@app.route('/api/environments', methods=['GET'])
def list_environments():
    """List all environments"""
    environments = db_manager.list_environments()
    return jsonify(environments)


@app.route('/api/environments', methods=['POST'])
def create_environment():
    """Create a new environment"""
    data = request.json
    
    required_fields = ['db_type', 'db_version']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    db_type = data['db_type']
    db_version = data['db_version']
    replication_type = data.get('replication_type', 'async')
    name = data.get('name')
    replica_count = int(data.get('replica_count', 1))
    
    # Validate inputs
    if db_type.lower() not in ['mysql', 'percona', 'mariadb']:
        return jsonify({'error': 'Invalid db_type. Must be mysql, percona, or mariadb'}), 400
    
    if replica_count < 1 or replica_count > 10:
        return jsonify({'error': 'replica_count must be between 1 and 10'}), 400
    
    env_data, result = db_manager.create_environment(
        db_type=db_type,
        db_version=db_version,
        replication_type=replication_type,
        name=name,
        replica_count=replica_count
    )
    
    if result['success']:
        return jsonify(env_data), 201
    else:
        return jsonify({
            'error': 'Failed to create environment',
            'details': result['stderr']
        }), 500


@app.route('/api/environments/<env_id>', methods=['GET'])
def get_environment(env_id):
    """Get environment details"""
    env_data = db_manager.get_environment(env_id)
    if env_data:
        return jsonify(env_data)
    return jsonify({'error': 'Environment not found'}), 404


@app.route('/api/environments/<env_id>', methods=['DELETE'])
def delete_environment(env_id):
    """Delete an environment"""
    import time
    start_time = time.time()
    
    result = db_manager.delete_environment(env_id)
    result['deletion_time'] = f"{time.time() - start_time:.2f}s"
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 500


@app.route('/api/environments/<env_id>/logs', methods=['GET'])
def get_environment_logs(env_id):
    """Get container logs for debugging"""
    env_data = db_manager.get_environment(env_id)
    if not env_data:
        return jsonify({'error': 'Environment not found'}), 404
    
    env_dir = ENVIRONMENTS_DIR / env_id
    logs = {}
    
    if 'containers' in env_data and env_data['containers']:
        for container_name in env_data['containers']:
            result = db_manager.run_docker_command(
                f'docker logs {container_name} --tail 100',
                cwd=env_dir
            )
            if result['success']:
                logs[container_name] = result['stdout']
            else:
                logs[container_name] = f"Error: {result['stderr']}"
    
    return jsonify(logs), 200


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

