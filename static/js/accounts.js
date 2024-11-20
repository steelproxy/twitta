class AccountManager {
    constructor() {
        this.modal = new bootstrap.Modal(document.getElementById('accountModal'));
        this.isEditing = false;
        this.botRunning = false;
        this.init();
    }

    init() {
        this.loadAccounts();
        this.setupEventListeners();
    }

    setupEventListeners() {
        document.getElementById('accountForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveAccount();
        });
    }

    loadAccounts() {
        fetch('/api/accounts')
            .then(response => response.json())
            .then(data => {
                this.botRunning = data.running;
                this.renderAccounts(data.accounts);
            });
    }

    renderAccounts(accounts) {
        const tbody = document.getElementById('accountsTable');
        tbody.innerHTML = accounts.length ? accounts.map(account => this.createAccountRow(account)).join('') 
            : '<tr><td colspan="5" class="text-center">No accounts configured</td></tr>';
    }

    createAccountRow(account) {
        return `
            <tr>
                <td>@${account.username}</td>
                <td>${account.use_gpt ? '✅' : '❌'}</td>
                <td>${account.custom_prompt || '(default)'}</td>
                <td>${(account.predefined_replies || []).length} replies</td>
                <td>
                    <button class="btn btn-sm btn-primary me-2" onclick='accountManager.editAccount("${account.username}")'>Edit</button>
                    <button class="btn btn-sm btn-danger" onclick='accountManager.deleteAccount("${account.username}")'>Delete</button>
                </td>
            </tr>
        `;
    }

    showAddModal() {
        this.isEditing = false;
        document.getElementById('modalTitle').textContent = 'Add Account';
        document.getElementById('accountForm').reset();
        document.getElementById('username').disabled = false;
        this.modal.show();
    }

    editAccount(username) {
        this.isEditing = true;
        fetch('/api/accounts')
            .then(response => response.json())
            .then(data => {
                const account = data.accounts.find(acc => acc.username === username);
                this.populateForm(account);
                this.modal.show();
            })
            .catch(error => alert('Error loading account details'));
    }

    populateForm(account) {
        document.getElementById('modalTitle').textContent = 'Edit Account';
        document.getElementById('username').value = account.username;
        document.getElementById('username').disabled = true;
        document.getElementById('useGpt').checked = account.use_gpt;
        document.getElementById('customPrompt').value = account.custom_prompt || '';
        document.getElementById('predefinedReplies').value = (account.predefined_replies || []).join('\n');
    }

    saveAccount() {
        const data = this.getFormData();
        fetch('/api/accounts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => this.handleSaveResponse(data));
    }

    getFormData() {
        return {
            username: document.getElementById('username').value.trim(),
            use_gpt: document.getElementById('useGpt').checked,
            custom_prompt: document.getElementById('customPrompt').value.trim(),
            predefined_replies: document.getElementById('predefinedReplies').value
                .split('\n')
                .map(line => line.trim())
                .filter(line => line.length > 0)
        };
    }

    handleSaveResponse(data) {
        if (data.status === 'success') {
            this.modal.hide();
            this.loadAccounts();
            if (data.restart_required) {
                document.getElementById('restartAlert').style.display = 'block';
            }
        } else {
            alert(data.message);
        }
    }

    deleteAccount(username) {
        if (!confirm(`Are you sure you want to delete @${username}?`)) return;

        fetch('/api/accounts', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        })
        .then(response => response.json())
        .then(data => this.handleDeleteResponse(data));
    }

    handleDeleteResponse(data) {
        if (data.status === 'success') {
            this.loadAccounts();
            if (data.restart_required) {
                document.getElementById('restartAlert').style.display = 'block';
            }
        } else {
            alert(data.message);
        }
    }
}

let accountManager;
document.addEventListener('DOMContentLoaded', () => {
    accountManager = new AccountManager();
}); 