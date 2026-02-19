/**
 * BD | AS Platform - Painel Geral de Vendas (Versão Pro)
 * Monitoramento multi-marketplace unificado com Analytics
 */

const VendasTemplate = () => {
    // Busca os dados do usuário do JWT para exibir no Header
    const token = localStorage.getItem('access_token');
    let storeDisplay = "Minha Loja";
    
    if (token) {
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            // Captura o valor de loja_permissao enviado pelo novo token
            storeDisplay = payload.loja_permissao || payload.sub || "Minha Loja";
        } catch (e) { 
            console.error("Erro ao decodificar token", e); 
        }
    }

    return `
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem;">
        <div class="header-content">
            <h1 style="color: #ffffff; margin-bottom: 5px;">💰 Painel de Vendas</h1>
            <p style="color: #a0a0a0; font-size: 0.9rem;">Organização: <strong style="color: #3b82f6;">${storeDisplay.toLowerCase()}</strong></p>
        </div>
        
        <div class="filters-bar" style="display: flex; gap: 10px; background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">
            <div class="filter-group">
                <small style="color: #888; display: block; margin-bottom: 4px;">Marketplace</small>
                <select id="filter-marketplace" onchange="initVendasPage()" style="background: #1a1c1e; color: white; border: 1px solid #444; padding: 5px 10px; border-radius: 5px; cursor: pointer;">
                    <option value="all">Todos</option>
                    <option value="mercadolivre">Mercado Livre</option>
                    <option value="shopee">Shopee (Breve)</option>
                </select>
            </div>
            <div class="filter-group">
                <small style="color: #888; display: block; margin-bottom: 4px;">De:</small>
                <input type="date" id="filter-start-date" 
                       onclick="this.showPicker()" 
                       onchange="initVendasPage()" 
                       style="background: #1a1c1e; color: white; border: 1px solid #444; padding: 5px 10px; border-radius: 5px; cursor: pointer;">
            </div>
            <div class="filter-group">
                <small style="color: #888; display: block; margin-bottom: 4px;">Até:</small>
                <input type="date" id="filter-end-date" 
                       onclick="this.showPicker()" 
                       onchange="initVendasPage()" 
                       style="background: #1a1c1e; color: white; border: 1px solid #444; padding: 5px 10px; border-radius: 5px; cursor: pointer;">
            </div>
        </div>
    </div>

    <div class="stats-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-bottom: 2rem; gap: 20px;">
        <div class="stat-card" style="background: #1a1c1e; border: 1px solid #333; padding: 20px; border-radius: 12px; border-top: 4px solid #3b82f6;">
            <span class="stat-label" style="color: #888; font-size: 0.8rem; text-transform: uppercase;">Volume Total Bruto</span>
            <h2 id="vendas-total-volume" style="color: #ffffff; margin: 10px 0; font-size: 1.6rem;">R$ 0,00</h2>
            <small id="vendas-total-count" style="color: #3b82f6;">0 pedidos no total</small>
        </div>
        <div class="stat-card" style="background: #1a1c1e; border: 1px solid #333; padding: 20px; border-radius: 12px; border-top: 4px solid #2ecc71;">
            <span class="stat-label" style="color: #888; font-size: 0.8rem; text-transform: uppercase;">Valor Faturado</span>
            <h2 id="vendas-faturado" style="color: #2ecc71; margin: 10px 0; font-size: 1.6rem;">R$ 0,00</h2>
            <small style="color: #555;">Status PAID/SHIPPED</small>
        </div>
        <div class="stat-card" style="background: #1a1c1e; border: 1px solid #333; padding: 20px; border-radius: 12px; border-top: 4px solid #e74c3c;">
            <span class="stat-label" style="color: #888; font-size: 0.8rem; text-transform: uppercase;">Valor Cancelado</span>
            <h2 id="vendas-cancelado" style="color: #e74c3c; margin: 10px 0; font-size: 1.6rem;">R$ 0,00</h2>
            <small style="color: #555;">Status CANCELLED</small>
        </div>
    </div>

    <div class="chart-section" style="background: #1a1c1e; border: 1px solid #333; padding: 20px; border-radius: 12px; margin-bottom: 2rem;">
        <h3 style="color: #fff; margin-bottom: 1.5rem; font-size: 1rem;">📈 Desempenho Diário (Valor Bruto)</h3>
        <div style="height: 300px; width: 100%;">
            <canvas id="salesChart"></canvas>
        </div>
    </div>

    <div class="results-section">
        <details open style="background: #1a1c1e; border: 1px solid #333; border-radius: 12px; padding: 10px;">
            <summary style="color: #ffffff; padding: 10px; cursor: pointer; font-weight: 600; display: flex; justify-content: space-between; align-items: center;">
                <span>📋 Histórico de Pedidos Recentes</span>
                <span style="font-size: 0.8rem; color: #555;">Clique para recolher lista</span>
            </summary>
            
            <div id="vendas-container" style="padding: 10px;">
                <div class="loading" style="color: #ffffff; text-align: center; padding: 2rem;">
                    <div class="spinner"></div>
                    <p>Buscando registros...</p>
                </div>
            </div>

            <div id="pagination-controls" style="display: flex; justify-content: center; gap: 10px; padding: 20px; border-top: 1px solid #333;">
            </div>
        </details>
    </div>
`};

let allOrders = []; 
let salesChart = null;
let currentPage = 1;
const ordersPerPage = 10;

async function initVendasPage() {
    const container = document.getElementById('vendas-container');
    const faturadoEl = document.getElementById('vendas-faturado');
    const canceladoEl = document.getElementById('vendas-cancelado');
    const volumeEl = document.getElementById('vendas-total-volume');
    const countEl = document.getElementById('vendas-total-count');

    try {
        if (allOrders.length === 0) {
            const response = await fetch('/api/webhooks/mercadolivre/orders', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
            });
            if (!response.ok) throw new Error('Erro ao carregar pedidos');
            allOrders = await response.json();
        }

        const filterMkt = document.getElementById('filter-marketplace').value;
        const filterStart = document.getElementById('filter-start-date').value;
        const filterEnd = document.getElementById('filter-end-date').value;

        let filtered = allOrders.filter(o => {
            const matchMkt = filterMkt === 'all' || o.marketplace === filterMkt;
            const orderDate = new Date(o.created_at).toISOString().split('T')[0];
            const matchStart = !filterStart || orderDate >= filterStart;
            const matchEnd = !filterEnd || orderDate <= filterEnd;
            return matchMkt && matchStart && matchEnd;
        });

        if (filtered.length === 0) {
            container.innerHTML = `<p style="color: #888; text-align: center; padding: 20px;">Nenhuma venda encontrada para o filtro aplicado.</p>`;
            return;
        }

        let valFaturado = 0;
        let valCancelado = 0;
        let valBruto = 0;

        filtered.forEach(o => {
            const amount = o.total_amount || 0;
            valBruto += amount;
            if (o.status === 'paid' || o.status === 'shipped') valFaturado += amount;
            if (o.status === 'cancelled') valCancelado += amount;
        });

        volumeEl.textContent = valBruto.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        faturadoEl.textContent = valFaturado.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        canceladoEl.textContent = valCancelado.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        countEl.textContent = `${filtered.length} pedidos encontrados`;

        updateSalesChart(filtered);
        renderOrdersList(filtered);

    } catch (error) {
        container.innerHTML = `<div style="color: #ff4d4d; padding: 20px;">Erro: ${error.message}</div>`;
    }
}

function renderOrdersList(orders) {
    const container = document.getElementById('vendas-container');
    const pagEl = document.getElementById('pagination-controls');
    
    const start = (currentPage - 1) * ordersPerPage;
    const paginated = orders.slice(start, start + ordersPerPage);
    const totalPages = Math.ceil(orders.length / ordersPerPage);

    container.innerHTML = paginated.map(order => {
        const data = order.raw_data || {};
        const brandColor = order.marketplace === 'mercadolivre' ? '#fff159' : '#3b82f6';
        const statusColor = order.status === 'paid' ? '#2ecc71' : (order.status === 'cancelled' ? '#e74c3c' : '#f1c40f');

        // Extração de Itens (Mercado Livre)
        const items = data.order_items || [];
        const productTitle = items.length > 0 ? items[0].item.title : "Produto não identificado";
        const quantity = items.reduce((acc, item) => acc + (item.quantity || 0), 0);
        const hasMoreItems = items.length > 1 ? ` (+${items.length - 1} outros)` : "";

        return `
        <div class="order-item" style="background: #0d0e10; border: 1px solid #222; border-left: 4px solid ${brandColor}; margin-bottom: 1.2rem; padding: 18px; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                <div>
                    <span style="font-size: 0.6rem; color: ${brandColor}; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;">${order.marketplace}</span>
                    <h4 style="color: #fff; margin: 2px 0; font-size: 1rem;">Pedido #${data.id || order.external_id}</h4>
                    
                    <div style="margin-top: 5px;">
                        <span style="color: #3b82f6; font-weight: 600; font-size: 0.95rem;">${productTitle}${hasMoreItems}</span>
                        <span style="color: #888; font-size: 0.85rem; margin-left: 8px;">(Qtd: ${quantity})</span>
                    </div>
                </div>
                <span style="background: ${statusColor}; color: #000; padding: 3px 12px; border-radius: 20px; font-size: 0.7rem; font-weight: 800;">
                    ${(order.status || 'N/A').toUpperCase()}
                </span>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px; padding-top: 10px; border-top: 1px solid #1a1c1e;">
                <div style="display: flex; gap: 20px; font-size: 0.85rem;">
                    <span style="color: #ccc;">👤 ${data.buyer?.nickname || 'Cliente'}</span>
                    <span style="color: #2ecc71; font-weight: 700;">💰 ${order.total_amount.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span>
                </div>
                <span style="color: #666; font-size: 0.8rem;">📅 ${new Date(order.created_at).toLocaleDateString('pt-BR')}</span>
            </div>

            <details style="margin-top: 1rem; border-top: 1px solid #222; padding-top: 10px;">
                <summary style="font-size: 0.7rem; color: #444; cursor: pointer; user-select: none;">Ver Payload Completo (JSON)</summary>
                <pre style="background: #000; color: #0fa; padding: 12px; border-radius: 6px; font-size: 0.7rem; margin-top: 10px; overflow-x: auto; border: 1px solid #111;">${JSON.stringify(data, null, 2)}</pre>
            </details>
        </div>`;
    }).join('');

    pagEl.innerHTML = totalPages > 1 ? `
        <button onclick="changePage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''} style="background: #222; color: #fff; border: none; padding: 5px 15px; border-radius: 4px; cursor: pointer;">Anterior</button>
        <span style="color: #888; align-self: center;">Página ${currentPage} de ${totalPages}</span>
        <button onclick="changePage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''} style="background: #222; color: #fff; border: none; padding: 5px 15px; border-radius: 4px; cursor: pointer;">Próxima</button>
    ` : '';
}

function changePage(page) {
    currentPage = page;
    initVendasPage();
}

function updateSalesChart(orders) {
    const ctx = document.getElementById('salesChart').getContext('2d');
    
    const dailyData = {};
    orders.forEach(o => {
        const date = new Date(o.created_at).toLocaleDateString('pt-BR');
        dailyData[date] = (dailyData[date] || 0) + o.total_amount;
    });

    const labels = Object.keys(dailyData).reverse();
    const data = Object.values(dailyData).reverse();

    if (salesChart) salesChart.destroy();

    salesChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Vendas Brutas (R$)',
                data: data,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointBackgroundColor: '#3b82f6'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#888' } },
                x: { grid: { display: false }, ticks: { color: '#888' } }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}