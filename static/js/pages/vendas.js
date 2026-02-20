/**
 * BD | AS Platform - Painel Geral de Vendas (Dashboard Multi-Nível)
 */

const VendasTemplate = () => {
    const token = localStorage.getItem('access_token');
    let storeDisplay = "Minha Loja";
    
    if (token) {
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            storeDisplay = payload.loja_permissao || payload.sub || "Minha Loja";
        } catch (e) { console.error("Erro ao decodificar token", e); }
    }

    return `
    <div class="page-header" style="margin-bottom: 2rem;">
        <h1 style="color: #ffffff; margin-bottom: 5px;">💰 Inteligência de Vendas</h1>
        <p style="color: #a0a0a0; font-size: 0.9rem;">Organização: <strong style="color: #3b82f6;">${storeDisplay.toLowerCase()}</strong></p>
    </div>

    <div style="margin-bottom: 1rem;">
        <h3 style="color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">🌍 Performance Consolidada (Geral)</h3>
        <div class="stats-grid-global" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
            <div class="stat-card" style="background: #1a1c1e; border: 1px solid #333; padding: 20px; border-radius: 12px; border-left: 4px solid #fff;">
                <span style="color: #888; font-size: 0.75rem;">VOL. TOTAL BRUTO</span>
                <h2 id="global-total-volume" style="color: #ffffff; margin: 8px 0; font-size: 1.4rem;">R$ 0,00</h2>
                <small id="global-total-count" style="color: #888;">0 pedidos</small>
            </div>
            <div class="stat-card" style="background: #1a1c1e; border: 1px solid #333; padding: 20px; border-radius: 12px; border-left: 4px solid #2ecc71;">
                <span style="color: #888; font-size: 0.75rem;">FATURADO GERAL</span>
                <h2 id="global-faturado" style="color: #2ecc71; margin: 8px 0; font-size: 1.4rem;">R$ 0,00</h2>
            </div>
            <div class="stat-card" style="background: #1a1c1e; border: 1px solid #333; padding: 20px; border-radius: 12px; border-left: 4px solid #e74c3c;">
                <span style="color: #888; font-size: 0.75rem;">CANCELADO GERAL</span>
                <h2 id="global-cancelado" style="color: #e74c3c; margin: 8px 0; font-size: 1.4rem;">R$ 0,00</h2>
            </div>
        </div>
    </div>

    <div class="filters-bar" style="display: flex; gap: 15px; background: rgba(59, 130, 246, 0.05); padding: 15px; border-radius: 12px; border: 1px solid rgba(59, 130, 246, 0.2); margin-bottom: 1.5rem; align-items: center;">
        <div class="filter-group" style="flex: 1;">
            <small style="color: #3b82f6; display: block; margin-bottom: 4px; font-weight: 600;">Filtrar Marketplace</small>
            <select id="filter-marketplace" onchange="initVendasPage()" style="width: 100%; background: #1a1c1e; color: white; border: 1px solid #333; padding: 8px; border-radius: 6px;">
                <option value="all">Todos os Canais</option>
                <option value="mercadolivre">Mercado Livre</option>
                <option value="magalu">Magalu</option>
            </select>
        </div>
        <div class="filter-group">
            <small style="color: #888; display: block; margin-bottom: 4px;">De:</small>
            <input type="date" id="filter-start-date" onchange="initVendasPage()" style="background: #1a1c1e; color: white; border: 1px solid #333; padding: 8px; border-radius: 6px;">
        </div>
        <div class="filter-group">
            <small style="color: #888; display: block; margin-bottom: 4px;">Até:</small>
            <input type="date" id="filter-end-date" onchange="initVendasPage()" style="background: #1a1c1e; color: white; border: 1px solid #333; padding: 8px; border-radius: 6px;">
        </div>
    </div>

    <div style="margin-bottom: 2rem;">
        <h3 style="color: #3b82f6; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;">🎯 Resultado do Filtro</h3>
        <div class="stats-grid-filtered" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
            <div class="stat-card" style="background: #0d0e10; border: 1px solid #3b82f6; padding: 20px; border-radius: 12px;">
                <span style="color: #3b82f6; font-size: 0.75rem; font-weight: 600;">VOLUME NO CANAL</span>
                <h2 id="filtered-total-volume" style="color: #ffffff; margin: 8px 0; font-size: 1.4rem;">R$ 0,00</h2>
                <small id="filtered-total-count" style="color: #888;">0 pedidos</small>
            </div>
            <div class="stat-card" style="background: #0d0e10; border: 1px solid #2ecc71; padding: 20px; border-radius: 12px;">
                <span style="color: #2ecc71; font-size: 0.75rem; font-weight: 600;">FATURADO NO CANAL</span>
                <h2 id="filtered-faturado" style="color: #ffffff; margin: 8px 0; font-size: 1.4rem;">R$ 0,00</h2>
            </div>
            <div class="stat-card" style="background: #0d0e10; border: 1px solid #e74c3c; padding: 20px; border-radius: 12px;">
                <span style="color: #e74c3c; font-size: 0.75rem; font-weight: 600;">CANCELADO NO CANAL</span>
                <h2 id="filtered-cancelado" style="color: #ffffff; margin: 8px 0; font-size: 1.4rem;">R$ 0,00</h2>
            </div>
        </div>
    </div>

    <div class="chart-section" style="background: #1a1c1e; border: 1px solid #333; padding: 20px; border-radius: 12px; margin-bottom: 2rem;">
        <h3 style="color: #fff; margin-bottom: 1.5rem; font-size: 0.9rem;">📈 Evolução Temporal (Filtro Ativo)</h3>
        <div style="height: 300px; width: 100%;"><canvas id="salesChart"></canvas></div>
    </div>

    <div class="results-section">
        <div style="background: #1a1c1e; border: 1px solid #333; border-radius: 12px; padding: 15px;">
            <h3 style="color: #ffffff; margin-bottom: 15px; font-size: 1rem; font-weight: 600;">📋 Detalhamento dos Pedidos</h3>
            <div id="vendas-container"></div>
            <div id="pagination-controls" style="display: flex; justify-content: center; gap: 10px; padding: 15px; border-top: 1px solid #333; margin-top: 10px;"></div>
        </div>
    </div>
`};

let allOrders = []; 
let salesChart = null;
let currentPage = 1;
const ordersPerPage = 10;

async function initVendasPage() {
    const container = document.getElementById('vendas-container');
    const gVol = document.getElementById('global-total-volume'), gFat = document.getElementById('global-faturado');
    const gCan = document.getElementById('global-cancelado'), gCnt = document.getElementById('global-total-count');
    const fVol = document.getElementById('filtered-total-volume'), fFat = document.getElementById('filtered-faturado');
    const fCan = document.getElementById('filtered-cancelado'), fCnt = document.getElementById('filtered-total-count');

    try {
        if (allOrders.length === 0) {
            const res = await fetch('/api/webhooks/mercadolivre/orders', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
            });
            allOrders = await res.json();
        }

        const mkt = document.getElementById('filter-marketplace').value;
        const start = document.getElementById('filter-start-date').value;
        const end = document.getElementById('filter-end-date').value;

        const globalSet = allOrders.filter(o => {
            const d = new Date(o.created_at).toISOString().split('T')[0];
            return (!start || d >= start) && (!end || d <= end);
        });

        let gV = 0, gF = 0, gC = 0;
        globalSet.forEach(o => {
            gV += o.total_amount || 0;
            if (['paid','shipped','approved'].includes(o.status)) gF += o.total_amount;
            if (['cancelled', 'refunded', 'returned'].includes(o.status)) gC += o.total_amount;
        });

        gVol.textContent = gV.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        gFat.textContent = gF.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        gCan.textContent = gC.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        gCnt.textContent = `${globalSet.length} pedidos realizados`;

        const filteredSet = globalSet.filter(o => mkt === 'all' || o.marketplace === mkt);
        let fV = 0, fF = 0, fC = 0;
        filteredSet.forEach(o => {
            fV += o.total_amount || 0;
            if (['paid','shipped','approved'].includes(o.status)) fF += o.total_amount;
            if (['cancelled', 'refunded', 'returned'].includes(o.status)) fC += o.total_amount;
        });

        fVol.textContent = fV.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        fFat.textContent = fF.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        fCan.textContent = fC.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
        fCnt.textContent = `${filteredSet.length} pedidos no canal`;

        updateSalesChart(filteredSet);
        renderOrdersList(filteredSet);
    } catch (e) { container.innerHTML = `<p style="color:red">Erro: ${e.message}</p>`; }
}

function renderOrdersList(orders) {
    const container = document.getElementById('vendas-container');
    const pagEl = document.getElementById('pagination-controls');
    const start = (currentPage - 1) * ordersPerPage;
    const paginated = orders.slice(start, start + ordersPerPage);
    const totalPages = Math.ceil(orders.length / ordersPerPage);

    container.innerHTML = paginated.map(order => {
        const data = order.raw_data || {};
        let brandColor = order.marketplace === 'mercadolivre' ? '#fff159' : (order.marketplace === 'magalu' ? '#0086ff' : '#3b82f6');
        const statusColor = ['paid', 'approved', 'shipped'].includes(order.status) ? '#2ecc71' : (['cancelled', 'refunded', 'returned'].includes(order.status) ? '#e74c3c' : '#f1c40f');
        // Extração de Produto e Qtd
        let productName = "Produto não identificado";
        let qty = 0;

        if (order.marketplace === 'mercadolivre') {
            const items = data.order_items || [];
            productName = items.length > 0 ? items[0].item.title : "Venda ML";
            qty = items.reduce((acc, i) => acc + (i.quantity || 0), 0);
        } else if (order.marketplace === 'magalu') {
            const items = data.items || [];
            productName = items.length > 0 ? items[0].name : "Venda Magalu";
            qty = items.reduce((acc, i) => acc + (i.quantity || 1), 0);
        }

        return `
        <div class="order-item" style="background: #0d0e10; border: 1px solid #222; border-left: 4px solid ${brandColor}; margin-bottom: 1rem; padding: 18px; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div>
                    <span style="font-size: 0.6rem; color: ${brandColor}; font-weight: 800; letter-spacing: 1px;">${order.marketplace.toUpperCase()}</span>
                    <h4 style="color: #fff; margin: 2px 0; font-size: 1rem;">Pedido #${order.external_id}</h4>
                </div>
                <span style="background: ${statusColor}; color: #000; padding: 4px 12px; border-radius: 6px; font-size: 0.7rem; font-weight: 800; white-space: nowrap; min-width: 80px; text-align: center;">
                    ${(order.status || 'N/A').toUpperCase()}
                </span>
            </div>

            <div style="margin-bottom: 15px;">
                <p style="color: #3b82f6; font-weight: 600; font-size: 0.9rem; margin-bottom: 4px;">${productName}</p>
                <span style="color: #888; font-size: 0.8rem;">Quantidade: <strong>${qty}</strong></span>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #1a1c1e; padding-top: 12px;">
                <span style="color: #2ecc71; font-weight: 700; font-size: 1rem;">${order.total_amount.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</span>
                <span style="color: #666; font-size: 0.8rem;">📅 ${new Date(order.created_at).toLocaleDateString('pt-BR')}</span>
            </div>

            <details style="margin-top: 12px;">
                <summary style="font-size: 0.75rem; color: #444; cursor: pointer; user-select: none; font-weight: 600;">ver detalhes técnicos (JSON)</summary>
                <pre style="background: #000; color: #0fa; padding: 12px; border-radius: 6px; font-size: 0.7rem; margin-top: 8px; overflow-x: auto; border: 1px solid #111;">${JSON.stringify(data, null, 2)}</pre>
            </details>
        </div>`;
    }).join('');

    pagEl.innerHTML = totalPages > 1 ? `
        <button onclick="changePage(${currentPage-1})" ${currentPage==1?'disabled':''} style="background:#222; color:#fff; border:none; padding:5px 12px; border-radius:4px; cursor:pointer;">Ant</button>
        <span style="color:#888; font-size:0.8rem;">${currentPage} / ${totalPages}</span>
        <button onclick="changePage(${currentPage+1})" ${currentPage==totalPages?'disabled':''} style="background:#222; color:#fff; border:none; padding:5px 12px; border-radius:4px; cursor:pointer;">Próx</button>
    ` : '';
}

function updateSalesChart(orders) {
    const ctx = document.getElementById('salesChart').getContext('2d');
    const daily = {};
    orders.forEach(o => {
        const d = new Date(o.created_at).toLocaleDateString('pt-BR');
        daily[d] = (daily[d] || 0) + o.total_amount;
    });
    const labels = Object.keys(daily).reverse();
    const data = Object.values(daily).reverse();
    if (salesChart) salesChart.destroy();
    salesChart = new Chart(ctx, {
        type: 'line',
        data: { 
            labels, 
            datasets: [{ 
                label: 'Faturamento (R$)', 
                data, 
                borderColor: '#3b82f6', 
                backgroundColor: 'rgba(59, 130, 246, 0.1)', 
                fill: true, 
                tension: 0.4 
            }] 
        },
        options: { 
            responsive: true, 
            maintainAspectRatio: false,
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#888' } },
                x: { grid: { display: false }, ticks: { color: '#888' } }
            }
        }
    });
}

function changePage(p) { currentPage = p; initVendasPage(); }