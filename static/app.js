const API_BASE = '/api';

// Load environments on page load
document.addEventListener('DOMContentLoaded', () => {
    refreshEnvironments();
});

function showCreateForm() {
    document.getElementById('create-form').classList.remove('hidden');
    document.getElementById('environments-list').classList.add('hidden');
}

function hideCreateForm() {
    document.getElementById('create-form').classList.add('hidden');
    document.getElementById('environments-list').classList.remove('hidden');
}

async function createEnvironment(event) {
    event.preventDefault();
    
    const formData = {
        name: document.getElementById('name').value.trim() || undefined,
        db_type: document.getElementById('db_type').value,
        db_version: document.getElementById('db_version').value,
        replication_type: document.getElementById('replication_type').value
    };
    
    try {
        const response = await fetch(`${API_BASE}/environments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('Environment created successfully!', 'success');
            hideCreateForm();
            document.getElementById('environment-form').reset();
            refreshEnvironments();
        } else {
            showAlert(`Error: ${data.error || 'Failed to create environment'}`, 'error');
        }
    } catch (error) {
        showAlert(`Error: ${error.message}`, 'error');
    }
}

async function refreshEnvironments() {
    const container = document.getElementById('environments');
    container.innerHTML = '<div class="loading">Loading environments...</div>';
    
    try {
        const response = await fetch(`${API_BASE}/environments`);
        const environments = await response.json();
        
        if (environments.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No environments yet</h3>
                    <p>Click "Create Environment" to get started</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = environments.map(env => createEnvironmentCard(env)).join('');
    } catch (error) {
        container.innerHTML = `<div class="alert alert-error">Error loading environments: ${error.message}</div>`;
    }
}

function createEnvironmentCard(env) {
    const statusClass = env.status || 'stopped';
    const createdDate = new Date(env.created_at).toLocaleString();
    
    return `
        <div class="environment-card ${statusClass}">
            <div class="environment-header">
                <div class="environment-name">${escapeHtml(env.name || env.id)}</div>
                <span class="status-badge ${statusClass}">${statusClass}</span>
            </div>
            <div class="environment-details">
                <div class="detail-row">
                    <span class="detail-label">Database Type:</span>
                    <span class="detail-value">${escapeHtml(env.db_type)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Version:</span>
                    <span class="detail-value">${escapeHtml(env.db_version)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Replication:</span>
                    <span class="detail-value">${escapeHtml(env.replication_type)}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Created:</span>
                    <span class="detail-value">${createdDate}</span>
                </div>
                ${env.containers && env.containers.length > 0 ? `
                <div class="detail-row">
                    <span class="detail-label">Containers:</span>
                    <span class="detail-value">${env.containers.length}</span>
                </div>
                ` : ''}
            </div>
            <div class="environment-actions">
                <button class="btn btn-danger btn-small" onclick="deleteEnvironment('${env.id}')">
                    🗑️ Delete
                </button>
                <button class="btn btn-success btn-small" onclick="viewEnvironment('${env.id}')">
                    👁️ View Details
                </button>
            </div>
        </div>
    `;
}

async function deleteEnvironment(envId) {
    if (!confirm('Are you sure you want to delete this environment? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/environments/${envId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAlert('Environment deleted successfully!', 'success');
            refreshEnvironments();
        } else {
            showAlert(`Error: ${data.error || 'Failed to delete environment'}`, 'error');
        }
    } catch (error) {
        showAlert(`Error: ${error.message}`, 'error');
    }
}

async function viewEnvironment(envId) {
    try {
        const response = await fetch(`${API_BASE}/environments/${envId}`);
        const env = await response.json();
        
        if (response.ok) {
            showEnvironmentModal(env);
        } else {
            showAlert(`Error: ${env.error || 'Failed to load environment'}`, 'error');
        }
    } catch (error) {
        showAlert(`Error: ${error.message}`, 'error');
    }
}

function showEnvironmentModal(env) {
    const modal = document.getElementById('modal');
    const modalBody = document.getElementById('modal-body');
    
    const createdDate = new Date(env.created_at).toLocaleString();
    
    modalBody.innerHTML = `
        <h2>Environment Details</h2>
        <div class="environment-details" style="margin-top: 20px;">
            <div class="detail-row">
                <span class="detail-label">ID:</span>
                <span class="detail-value">${escapeHtml(env.id)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Name:</span>
                <span class="detail-value">${escapeHtml(env.name || env.id)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Database Type:</span>
                <span class="detail-value">${escapeHtml(env.db_type)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Version:</span>
                <span class="detail-value">${escapeHtml(env.db_version)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Replication Type:</span>
                <span class="detail-value">${escapeHtml(env.replication_type)}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Status:</span>
                <span class="detail-value">
                    <span class="status-badge ${env.status}">${env.status}</span>
                </span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Created:</span>
                <span class="detail-value">${createdDate}</span>
            </div>
            ${env.containers && env.containers.length > 0 ? `
            <div class="detail-row">
                <span class="detail-label">Containers:</span>
                <span class="detail-value">
                    <ul style="list-style: none; padding: 0; margin: 5px 0;">
                        ${env.containers.map(c => `<li>• ${escapeHtml(c)}</li>`).join('')}
                    </ul>
                </span>
            </div>
            ` : ''}
            ${env.error ? `
            <div class="alert alert-error" style="margin-top: 15px;">
                <strong>Error:</strong> ${escapeHtml(env.error)}
            </div>
            ` : ''}
        </div>
        <div style="margin-top: 20px;">
            <h3>Connection Information</h3>
            <div class="alert alert-info" style="margin-top: 10px;">
                <strong>Source:</strong> localhost:3306<br>
                <strong>Replica:</strong> localhost:3307<br>
                <strong>Root Password:</strong> root_password<br>
                <strong>Replication User:</strong> repl<br>
                <strong>Replication Password:</strong> repl_password
            </div>
        </div>
    `;
    
    modal.classList.add('show');
    modal.classList.remove('hidden');
}

function closeModal() {
    const modal = document.getElementById('modal');
    modal.classList.remove('show');
    modal.classList.add('hidden');
}

function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const contentArea = document.querySelector('.content-area');
    contentArea.insertBefore(alertDiv, contentArea.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('modal');
    if (event.target === modal) {
        closeModal();
    }
}

