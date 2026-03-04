/**
 * static/js/pages/monitoring.js
 * Módulo de Monitoramento de Estoque - Versão Analítica com Paginação
 */

// Estado local da página para controle de paginação
let monitoringState = {
    allProducts: [],
    currentPage: 1,
    itemsPerPage: 20
};

// --- Templates ---
const MonitoringConfigTemplate = () => `
    <div class="page-header">
        <h1>⚙️ Configurações de Monitoramento</h1>
        <p>Gerencie os termos de busca para monitoramento automático na Leroy Merlin.</p>
    </div>

    <div class="upload-section">
        <h2>Cadastrar Novo Termo</h2>
        <div style="display: flex; gap: 1rem; margin-top: 1rem;">
            <input type="text" id="newTermInput" placeholder="Ex: gazebo articulado" 
                   style="flex: 1; padding: 0.8rem; background: #0f172a; border: 1px solid #334155; border-radius: 8px; color: white; outline: none;">
            <button class="btn btn-add" id="addTermBtn" style="padding: 0 2rem;">
                <span>➕</span> Adicionar
            </button>
        </div>
    </div>

    <div class="results-section">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
            <h2>📋 Termos Monitorados</h2>
            <button class="btn btn-primary" id="syncNowBtn" style="background: #10b981; border-color: #10b981;">
                <span>🔄</span> Sincronizar Agora
            </button>
        </div>
        <div class="bg-secondary rounded-xl overflow-hidden border border-white/10">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead style="background: rgba(255,255,255,0.05); color: var(--text-secondary); font-size: 0.75rem; text-transform: uppercase;">
                    <tr>
                        <th style="padding: 1rem;">Termo</th>
                        <th style="padding: 1rem;">Status</th>
                        <th style="padding: 1rem;">Última Varredura</th>
                        <th style="padding: 1rem; text-align: right;">Ações</th>
                    </tr>
                </thead>
                <tbody id="termsListBody" style="font-size: 0.875rem;">
                </tbody>
            </table>
        </div>
    </div>
`;

const MonitoringDashboardTemplate = () => `
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="color: #fff;">🛡️ Performance de Estoque</h1>
            <p style="color: #888;">Análise de escoamento ordenada por volume de vendas.</p>
        </div>
        <div style="min-width: 250px;">
            <select id="termSelector" style="width: 100%; padding: 10px; background: #1e293b; color: white; border: 1px solid #334155; border-radius: 8px; outline: none;">
                <option value="">Carregando termos...</option>
            </select>
        </div>
    </div>

    <div id="monSummaryCards" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem;">
    </div>

    <div class="results-section" style="padding: 0; background: transparent; border: none; box-shadow: none;">
        <div class="bg-secondary rounded-xl overflow-hidden border border-white/10" style="background: #1a1c1e;">
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead style="background: rgba(255,255,255,0.03); color: #888; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;">
                    <tr>
                        <th style="padding: 1.2rem 1.5rem;">Informações do Produto</th>
                        <th style="padding: 1.2rem 1.5rem; text-align: center;">Preço</th>
                        <th style="padding: 1.2rem 1.5rem; text-align: center;">Estoque Atual</th>
                        <th style="padding: 1.2rem 1.5rem; text-align: center;">Saída (Vendas)</th>
                        <th style="padding: 1.2rem 1.5rem; text-align: center;">Status</th>
                        <th style="padding: 1.2rem 1.5rem; text-align: right;">Ações</th>
                    </tr>
                </thead>
                <tbody id="monProductsTableBody" style="color: #eee; font-size: 0.85rem;">
                    <tr>
                        <td colspan="6" style="padding: 3rem; text-align: center; color: #666;">
                            Selecione um termo acima para visualizar os dados.
                        </td>
                    </tr>
                </tbody>
            </table>
            
            <div id="paginationControls" style="padding: 1rem; display: flex; justify-content: center; gap: 1rem; align-items: center; background: rgba(0,0,0,0.2); border-top: 1px solid rgba(255,255,255,0.05);">
            </div>
        </div>
    </div>
`;

// --- Funções de Inicialização ---

async function initMonitoringConfigPage() {
    const btnAdd = document.getElementById('addTermBtn');
    const input = document.getElementById('newTermInput');
    const btnSync = document.getElementById('syncNowBtn');
    const token = localStorage.getItem('access_token');

    const loadTerms = async () => {
        try {
            const res = await axios.get('/api/monitoring/terms', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const tbody = document.getElementById('termsListBody');
            tbody.innerHTML = res.data.map(t => `
                <tr style="border-top: 1px solid rgba(255,255,255,0.05);">
                    <td style="padding: 1rem; font-weight: 600;">${t.term}</td>
                    <td style="padding: 1rem;"><span style="color: #10b981;">● Ativo</span></td>
                    <td style="padding: 1rem; color: #888;">
                        ${t.last_run ? new Date(t.last_run).toLocaleString('pt-BR') : 'Aguardando sync'}
                    </td>
                    <td style="padding: 1rem; text-align: right;">
                        <button onclick="deleteMonTerm(${t.id})" class="remove-btn" style="padding: 5px 10px; cursor:pointer;">🗑️</button>
                    </td>
                </tr>
            `).join('');
        } catch (err) { console.error(err); }
    };

    btnAdd.onclick = async () => {
        const term = input.value.trim();
        if (!term) return;
        try {
            await axios.post('/api/monitoring/terms', { term: term, marketplace: 'leroy_merlin' }, { headers: { 'Authorization': `Bearer ${token}` } });
            input.value = '';
            loadTerms();
        } catch (err) { alert("Erro ao adicionar termo."); }
    };

    btnSync.onclick = async () => {
        btnSync.disabled = true;
        btnSync.innerHTML = '<span>⏳</span> Sincronizando...';
        try {
            await axios.post('/api/monitoring/sync', {}, { headers: { 'Authorization': `Bearer ${token}` } });
            alert("Sincronização concluída!");
            loadTerms();
        } catch (err) { alert("Erro na sincronização."); }
        finally {
            btnSync.disabled = false;
            btnSync.innerHTML = '<span>🔄</span> Sincronizar Agora';
        }
    };

    window.deleteMonTerm = async (id) => {
        if (await window.showConfirmModal("Deseja excluir este monitoramento?")) {
            await axios.delete(`/api/monitoring/terms/${id}`, { headers: { 'Authorization': `Bearer ${token}` } });
            loadTerms();
        }
    };
    loadTerms();
}

async function initMonitoringDashboardPage() {
    const selector = document.getElementById('termSelector');
    const token = localStorage.getItem('access_token');

    try {
        const termsRes = await axios.get('/api/monitoring/terms', { headers: { 'Authorization': `Bearer ${token}` } });
        selector.innerHTML = '<option value="">Escolha um termo para analisar...</option>' + 
            termsRes.data.map(t => `<option value="${t.id}">${t.term.toUpperCase()}</option>`).join('');
    } catch (err) { console.error(err); }

    selector.onchange = async () => {
        if (!selector.value) return;
        const tbody = document.getElementById('monProductsTableBody');
        tbody.innerHTML = '<tr><td colspan="6" style="padding: 3rem; text-align: center; color: #3b82f6;">⏳ Calculando performance de estoque...</td></tr>';

        try {
            const res = await axios.get(`/api/monitoring/dashboard-data/${selector.value}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            // Armazena no estado para paginação
            monitoringState.allProducts = res.data.products;
            monitoringState.currentPage = 1;
            
            renderSummaryCards(res.data.summary);
            renderMonitoringTable();
            
        } catch (err) { 
            console.error(err);
            tbody.innerHTML = '<tr><td colspan="6" style="padding: 3rem; text-align: center; color: #ef4444;">❌ Erro ao carregar dados do servidor.</td></tr>';
        }
    };
}

function renderSummaryCards(summary) {
    document.getElementById('monSummaryCards').innerHTML = `
        <div class="stat-card" style="background: #1a1c1e; border: 1px solid #333; padding: 1.5rem; border-radius: 12px; border-left: 4px solid #3b82f6;">
            <span style="font-size: 0.65rem; color: #888; font-weight: bold; text-transform: uppercase;">Produtos Monitorados</span>
            <h2 style="margin: 5px 0; color: #ffffff; font-size: 1.8rem;">${summary.total_products}</h2>
        </div>
        <div class="stat-card" style="background: #1a1c1e; border: 1px solid #333; padding: 1.5rem; border-radius: 12px; border-left: 4px solid #10b981;">
            <span style="font-size: 0.65rem; color: #888; font-weight: bold; text-transform: uppercase;">Saída Est. (24h)</span>
            <h2 style="margin: 5px 0; color: #10b981; font-size: 1.8rem;">${summary.estimated_sales_24h} un.</h2>
        </div>
        <div class="stat-card" style="background: #1a1c1e; border: 1px solid #333; padding: 1.5rem; border-radius: 12px; border-left: 4px solid #ef4444;">
            <span style="font-size: 0.65rem; color: #888; font-weight: bold; text-transform: uppercase;">Produtos Esgotados</span>
            <h2 style="margin: 5px 0; color: #ef4444; font-size: 1.8rem;">${summary.out_of_stock_count}</h2>
        </div>
    `;
}

function renderMonitoringTable() {
    const tbody = document.getElementById('monProductsTableBody');
    const pagination = document.getElementById('paginationControls');
    
    const start = (monitoringState.currentPage - 1) * monitoringState.itemsPerPage;
    const end = start + monitoringState.itemsPerPage;
    const paginatedItems = monitoringState.allProducts.slice(start, end);
    const totalPages = Math.ceil(monitoringState.allProducts.length / monitoringState.itemsPerPage);

    if (paginatedItems.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="padding: 3rem; text-align: center; color: #888;">Nenhum produto encontrado.</td></tr>';
        pagination.innerHTML = '';
        return;
    }

    tbody.innerHTML = paginatedItems.map(p => {
        const statusConfig = {
            'disponivel': { color: '#10b981', label: 'Em Estoque' },
            'critico': { color: '#f59e0b', label: 'Estoque Baixo' },
            'esgotado': { color: '#ef4444', label: 'Esgotado' }
        };
        const config = statusConfig[p.status] || statusConfig['disponivel'];

        return `
            <tr style="border-top: 1px solid rgba(255,255,255,0.03); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.02)'" onmouseout="this.style.background='transparent'">
                <td style="padding: 1.2rem 1.5rem;">
                    <div style="font-weight: 600; color: #fff; margin-bottom: 2px; font-size: 0.9rem;">${p.name}</div>
                    <div style="font-size: 0.65rem; color: #666; font-family: monospace;">ID: ${p.product_id}</div>
                </td>
                <td style="padding: 1rem 1.5rem; text-align: center; font-weight: 500;">
                    ${p.price > 0 ? p.price.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'}) : 'Sob consulta'}
                </td>
                <td style="padding: 1rem 1.5rem; text-align: center; font-weight: 700; font-size: 1.1rem; color: #fff;">
                    ${p.stock} <small style="font-weight: 400; color: #666; font-size: 0.7rem;">un.</small>
                </td>
                <td style="padding: 1rem 1.5rem; text-align: center;">
                    ${p.delta > 0 
                        ? `<span style="background: rgba(249, 115, 22, 0.15); color: #f97316; padding: 6px 12px; border-radius: 20px; font-weight: 800; font-size: 0.8rem;">🔥 ${p.delta}</span>` 
                        : `<span style="color: #444; font-weight: 600;">-</span>`
                    }
                </td>
                <td style="padding: 1rem 1.5rem; text-align: center;">
                    <div style="display: flex; align-items: center; justify-content: center; gap: 6px;">
                        <span style="width: 8px; height: 8px; border-radius: 50%; background: ${config.color};"></span>
                        <span style="color: ${config.color}; font-weight: 600; font-size: 0.75rem; text-transform: uppercase;">${config.label}</span>
                    </div>
                </td>
                <td style="padding: 1rem 1.5rem; text-align: right;">
                    <a href="${p.url}" target="_blank" class="btn btn-secondary" style="padding: 6px 12px; font-size: 0.75rem; background: #334155;">
                        <span>🔗</span> Abrir Leroy
                    </a>
                </td>
            </tr>
        `;
    }).join('');

    // Renderiza controles de página
    pagination.innerHTML = `
        <button onclick="changeMonPage(${monitoringState.currentPage - 1})" 
                ${monitoringState.currentPage === 1 ? 'disabled' : ''} 
                style="padding: 6px 15px; background: #334155; border: none; border-radius: 6px; color: #fff; cursor: pointer; opacity: ${monitoringState.currentPage === 1 ? '0.5' : '1'}">
            Anterior
        </button>
        <span style="color: #888; font-size: 0.8rem;">Página <b>${monitoringState.currentPage}</b> de <b>${totalPages}</b></span>
        <button onclick="changeMonPage(${monitoringState.currentPage + 1})" 
                ${monitoringState.currentPage === totalPages ? 'disabled' : ''} 
                style="padding: 6px 15px; background: #334155; border: none; border-radius: 6px; color: #fff; cursor: pointer; opacity: ${monitoringState.currentPage === totalPages ? '0.5' : '1'}">
            Próxima
        </button>
    `;
}

// Função global para troca de página
window.changeMonPage = (newPage) => {
    const totalPages = Math.ceil(monitoringState.allProducts.length / monitoringState.itemsPerPage);
    if (newPage < 1 || newPage > totalPages) return;
    monitoringState.currentPage = newPage;
    renderMonitoringTable();
    window.scrollTo({ top: 0, behavior: 'smooth' });
};