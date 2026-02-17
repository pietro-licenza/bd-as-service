/**
 * BD | AS Platform - AI Custos Dashboard com Filtro
 */

const DashboardTemplate = () => `
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 1rem;">
        <div>
            <h1>💰 AI - Custos</h1>
            <p>Monitoramento analítico de investimentos e consumo de tokens por plataforma.</p>
        </div>
        
        <div class="upload-section" style="margin-bottom: 0; padding: 1.2rem; display: flex; align-items: center; gap: 1.2rem; border: 1px solid rgba(255,255,255,0.05);">
            <div style="display: flex; flex-direction: column; gap: 0.3rem;">
                <label style="font-size: 0.75rem; color: var(--text-secondary); font-weight: 500;">Início</label>
                <input type="date" id="dash-start-date" style="background: #0f172a; border: 1px solid var(--border-color); color: white; padding: 6px 12px; border-radius: 6px; font-family: inherit;">
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.3rem;">
                <label style="font-size: 0.75rem; color: var(--text-secondary); font-weight: 500;">Fim</label>
                <input type="date" id="dash-end-date" style="background: #0f172a; border: 1px solid var(--border-color); color: white; padding: 6px 12px; border-radius: 6px; font-family: inherit;">
            </div>
            <button class="btn btn-primary" id="btn-filter-dash" style="padding: 10px 20px; margin-top: 18px; background: #3b82f6;">
                <span>🔍</span> Filtrar
            </button>
        </div>
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; margin-bottom: 2rem;">
        <div class="upload-section" style="margin-bottom:0; display:flex; flex-direction:column; align-items:center; justify-content:center; padding: 2rem;">
            <span style="color: var(--text-secondary); font-size: 0.9rem; font-weight: 500;">Investimento no Período</span>
            <h2 id="total-cost-val" style="font-size: 2.2rem; color: #10b981; margin: 0.5rem 0;">R$ 0,00</h2>
        </div>
        <div class="upload-section" style="margin-bottom:0; display:flex; flex-direction:column; align-items:center; justify-content:center; padding: 2rem;">
            <span style="color: var(--text-secondary); font-size: 0.9rem; font-weight: 500;">Tokens Processados</span>
            <h2 id="total-tokens-val" style="font-size: 2.2rem; color: #3b82f6; margin: 0.5rem 0;">0</h2>
        </div>
        <div class="upload-section" style="margin-bottom:0; display:flex; flex-direction:column; align-items:center; justify-content:center; padding: 2rem;">
            <span style="color: var(--text-secondary); font-size: 0.9rem; font-weight: 500;">Total de Requisições</span>
            <h2 id="total-reqs-val" style="font-size: 2.2rem; color: #f59e0b; margin: 0.5rem 0;">0</h2>
        </div>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem;">
        <div class="upload-section" style="padding: 1.5rem;">
            <h3 style="margin-bottom: 1.5rem; font-size: 1.2rem; color: #f1f5f9;">Custos por Integração</h3>
            <div style="height: 350px; display: flex; justify-content: center;">
                <canvas id="storeChart"></canvas>
            </div>
        </div>
        <div class="upload-section" style="padding: 1.5rem;">
            <h3 style="margin-bottom: 1.5rem; font-size: 1.2rem; color: #f1f5f9;">Investimento Diário</h3>
            <div style="height: 350px;">
                <canvas id="historyChart"></canvas>
            </div>
        </div>
    </div>
`;

let currentCharts = {}; 

async function initDashboardPage() {
    const btnFilter = document.getElementById('btn-filter-dash');
    const startInput = document.getElementById('dash-start-date');
    const endInput = document.getElementById('dash-end-date');

    const today = new Date().toISOString().split('T')[0];
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    startInput.value = weekAgo;
    endInput.value = today;

    btnFilter.addEventListener('click', () => loadStats(startInput.value, endInput.value));
    loadStats(weekAgo, today);
}

async function loadStats(start, end) {
    const costEl = document.getElementById('total-cost-val');
    const tokenEl = document.getElementById('total-tokens-val');
    const reqEl = document.getElementById('total-reqs-val');
    const chartTextColor = '#f1f5f9';

    try {
        const response = await fetch(`/api/dashboard/stats?start_date=${start}&end_date=${end}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });
        const data = await response.json();

        costEl.textContent = data.summary.total_cost.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', minimumFractionDigits: 4 });
        tokenEl.textContent = data.summary.total_tokens.toLocaleString('pt-BR');
        reqEl.textContent = data.summary.total_requests;

        if (currentCharts.store) currentCharts.store.destroy();
        if (currentCharts.history) currentCharts.history.destroy();

        const storeColors = { 'sams_club': '#475569', 'leroy_merlin': '#00A859', 'sodimac': '#FF6B35' };

        currentCharts.store = new Chart(document.getElementById('storeChart'), {
            type: 'doughnut',
            data: {
                labels: Object.keys(data.by_store).map(s => s.replace('_', ' ').toUpperCase()),
                datasets: [{
                    data: Object.values(data.by_store),
                    backgroundColor: Object.keys(data.by_store).map(s => storeColors[s] || '#334155'),
                    borderWidth: 0, hoverOffset: 15
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom', labels: { color: chartTextColor, font: { family: 'Poppins', size: 12 }, padding: 20 } } }
            }
        });

        currentCharts.history = new Chart(document.getElementById('historyChart'), {
            type: 'bar',
            data: {
                labels: data.history.map(h => h.date.split('-').reverse().slice(0,2).join('/')),
                datasets: [{ label: 'Investimento (R$)', data: data.history.map(h => h.cost), backgroundColor: 'rgba(59, 130, 246, 0.8)', borderRadius: 6 }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: chartTextColor, font: { family: 'Poppins' } } },
                    x: { grid: { display: false }, ticks: { color: chartTextColor, font: { family: 'Poppins' } } }
                },
                plugins: { legend: { display: false } }
            }
        });
    } catch (e) { console.error("Erro no loadStats:", e); }
}