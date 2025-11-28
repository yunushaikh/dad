#!/usr/bin/env python3
"""
DAD - Database Administration Dashboard
Backend Flask API for managing database testing environments
"""

import os
import json
import subprocess
import yaml
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
    
    def create_environment(self, db_type, db_version, replication_type='async', name=None):
        """Create a new database environment"""
        env_id = f"{db_type}_{db_version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if name:
            env_id = f"{name}_{env_id}"
        
        env_data = {
            'id': env_id,
            'db_type': db_type,
            'db_version': db_version,
            'replication_type': replication_type,
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
            f'docker-compose -f {compose_path} up -d',
            cwd=env_dir
        )
        
        if result['success']:
            env_data['status'] = 'running'
            # Get container names
            containers_result = self.run_docker_command(
                f'docker-compose -f {compose_path} ps --format json',
                cwd=env_dir
            )
            if containers_result['success']:
                try:
                    containers = json.loads(containers_result['stdout'])
                    env_data['containers'] = [c.get('Name', '') for c in containers if isinstance(c, dict)]
                except:
                    pass
        else:
            env_data['status'] = 'error'
            env_data['error'] = result['stderr']
        
        self.save_environment(env_data)
        return env_data, result
    
    def generate_compose_file(self, env_data):
        """Generate Docker Compose file based on environment configuration"""
        db_type = env_data['db_type'].lower()
        version = env_data['db_version']
        replication_type = env_data['replication_type']
        
        # Load base template
        template_dir = DOCKER_TEMPLATES_DIR / db_type
        template_file = template_dir / f'{replication_type}_replication.yml'
        
        if template_file.exists():
            with open(template_file, 'r') as f:
                compose_data = yaml.safe_load(f)
        else:
            # Generate default async replication template
            compose_data = self._generate_default_async_template(db_type, version)
        
        # Replace version placeholders
        compose_str = yaml.dump(compose_data)
        compose_str = compose_str.replace('${DB_VERSION}', version)
        compose_str = compose_str.replace('${ENV_ID}', env_data['id'])
        compose_data = yaml.safe_load(compose_str)
        
        return compose_data
    
    def _generate_default_async_template(self, db_type, version):
        """Generate default async replication template"""
        # Determine image based on db_type
        image_map = {
            'mysql': f'mysql:{version}',
            'percona': f'percona/percona-server:{version}',
            'mariadb': f'mariadb:{version}'
        }
        
        image = image_map.get(db_type.lower(), f'mysql:{version}')
        
        # Generate root password
        root_password = f"root_{datetime.now().strftime('%Y%m%d')}"
        
        return {
            'version': '3.8',
            'services': {
                'source': {
                    'image': image,
                    'container_name': f'${ENV_ID}_source',
                    'environment': {
                        'MYSQL_ROOT_PASSWORD': root_password,
                        'MYSQL_REPLICATION_MODE': 'master',
                        'MYSQL_REPLICATION_USER': 'repl',
                        'MYSQL_REPLICATION_PASSWORD': 'repl_password'
                    },
                    'ports': ['3306:3306'],
                    'volumes': [
                        'source_data:/var/lib/mysql',
                        './init_source.sql:/docker-entrypoint-initdb.d/init.sql'
                    ],
                    'command': self._get_replication_command(db_type, 'source'),
                    'networks': ['db_network']
                },
                'replica': {
                    'image': image,
                    'container_name': f'${ENV_ID}_replica',
                    'depends_on': ['source'],
                    'environment': {
                        'MYSQL_ROOT_PASSWORD': root_password,
                        'MYSQL_REPLICATION_MODE': 'slave',
                        'MYSQL_REPLICATION_USER': 'repl',
                        'MYSQL_REPLICATION_PASSWORD': 'repl_password',
                        'MYSQL_MASTER_HOST': 'source'
                    },
                    'ports': ['3307:3306'],
                    'volumes': [
                        'replica_data:/var/lib/mysql',
                        './init_replica.sql:/docker-entrypoint-initdb.d/init.sql'
                    ],
                    'command': self._get_replication_command(db_type, 'replica'),
                    'networks': ['db_network']
                }
            },
            'volumes': {
                'source_data': {},
                'replica_data': {}
            },
            'networks': {
                'db_network': {
                    'driver': 'bridge'
                }
            }
        }
    
    def _get_replication_command(self, db_type, role):
        """Get replication command based on database type and role"""
        if db_type.lower() == 'mysql':
            if role == 'source':
                return [
                    '--server-id=1',
                    '--log-bin=mysql-bin',
                    '--binlog-format=ROW',
                    '--gtid-mode=ON',
                    '--enforce-gtid-consistency=ON'
                ]
            else:
                return [
                    '--server-id=2',
                    '--relay-log=replica-relay-bin',
                    '--read-only=1'
                ]
        elif db_type.lower() == 'percona':
            if role == 'source':
                return [
                    '--server-id=1',
                    '--log-bin=mysql-bin',
                    '--binlog-format=ROW',
                    '--gtid-mode=ON',
                    '--enforce-gtid-consistency=ON'
                ]
            else:
                return [
                    '--server-id=2',
                    '--relay-log=replica-relay-bin',
                    '--read-only=1'
                ]
        elif db_type.lower() == 'mariadb':
            if role == 'source':
                return [
                    '--server-id=1',
                    '--log-bin=mysql-bin',
                    '--binlog-format=ROW'
                ]
            else:
                return [
                    '--server-id=2',
                    '--relay-log=replica-relay-bin',
                    '--read-only=1'
                ]
        return []
    
    def _create_init_scripts(self, env_dir, env_data):
        """Create SQL initialization scripts for replication setup"""
        db_type = env_data['db_type'].lower()
        
        # Source initialization script
        source_init = f"""-- Source (Master) initialization script
CREATE USER IF NOT EXISTS 'repl'@'%' IDENTIFIED BY 'repl_password';
GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';
FLUSH PRIVILEGES;
"""
        
        # Replica initialization script (will be run after source is ready)
        replica_init = f"""-- Replica initialization script
-- This will be configured after source is ready
"""
        
        with open(env_dir / 'init_source.sql', 'w') as f:
            f.write(source_init)
        
        with open(env_dir / 'init_replica.sql', 'w') as f:
            f.write(replica_init)
    
    def delete_environment(self, env_id):
        """Delete a database environment"""
        if env_id not in self.environments:
            return {'success': False, 'error': 'Environment not found'}
        
        env_dir = ENVIRONMENTS_DIR / env_id
        compose_path = env_dir / 'docker-compose.yml'
        
        if compose_path.exists():
            # Stop and remove containers
            result = self.run_docker_command(
                f'docker-compose -f {compose_path} down -v',
                cwd=env_dir
            )
            
            if not result['success']:
                return result
        
        # Remove environment directory
        if env_dir.exists():
            import shutil
            shutil.rmtree(env_dir)
        
        # Remove from memory and disk
        del self.environments[env_id]
        self.delete_environment_file(env_id)
        
        return {'success': True, 'message': 'Environment deleted successfully'}
    
    def list_environments(self):
        """List all environments"""
        # Update status for each environment
        for env_id, env_data in self.environments.items():
            env_dir = ENVIRONMENTS_DIR / env_id
            compose_path = env_dir / 'docker-compose.yml'
            
            if compose_path.exists():
                result = self.run_docker_command(
                    f'docker-compose -f {compose_path} ps --format json',
                    cwd=env_dir
                )
                if result['success']:
                    try:
                        containers = json.loads(result['stdout'])
                        running = sum(1 for c in containers if isinstance(c, dict) and c.get('State') == 'running')
                        if running > 0:
                            env_data['status'] = 'running'
                        else:
                            env_data['status'] = 'stopped'
                    except:
                        pass
        
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
    
    # Validate db_type
    if db_type.lower() not in ['mysql', 'percona', 'mariadb']:
        return jsonify({'error': 'Invalid db_type. Must be mysql, percona, or mariadb'}), 400
    
    env_data, result = db_manager.create_environment(
        db_type=db_type,
        db_version=db_version,
        replication_type=replication_type,
        name=name
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
    result = db_manager.delete_environment(env_id)
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 500


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

