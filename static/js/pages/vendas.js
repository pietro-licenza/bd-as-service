/**
 * BD | AS Platform - Painel Geral de Vendas
 * Monitoramento multi-marketplace unificado
 */

const VendasTemplate = () => `
    <div class="page-header">
        <div class="header-content">
            <h1 style="color: #ffffff;">💰 Painel de Vendas</h1>
            <p style="color: #e0e0e0;">Acompanhamento consolidado de novos pedidos em todos os marketplaces.</p>
        </div>
    </div>

    <div class="stats-grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-bottom: 2rem; gap: 20px;">
        <div class="stat-card" style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 20px; border-radius: 12px;">
            <div class="stat-icon" style="background: rgba(59, 130, 246, 0.2); color: #3b82f6; font-size: 1.5rem; margin-bottom: 10px;">📦</div>
            <div class="stat-info">
                <span class="stat-label" style="color: #bbbbbb; font-size: 0.85rem; display: block;">Total de Pedidos</span>
                <span class="stat-value" id="vendas-total-count" style="color: #ffffff; font-size: 1.8rem; font-weight: 700;">-</span>
            </div>
        </div>
        <div class="stat-card" style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 20px; border-radius: 12px;">
            <div class="stat-icon" style="background: rgba(39, 174, 96, 0.2); color: #2ecc71; font-size: 1.5rem; margin-bottom: 10px;">💵</div>
            <div class="stat-info">
                <span class="stat-label" style="color: #bbbbbb; font-size: 0.85rem; display: block;">Volume Total Bruto</span>
                <span class="stat-value" id="vendas-total-volume" style="color: #ffffff; font-size: 1.8rem; font-weight: 700;">R$ 0,00</span>
            </div>
        </div>
    </div>

    <div class="results-section">
        <div class="section-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
            <h2 style="color: #ffffff; margin: 0;">📋 Histórico de Pedidos</h2>
            <button class="btn-secondary" onclick="initVendasPage()" style="padding: 0.6rem 1.2rem; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">
                🔄 Atualizar Lista
            </button>
        </div>
        
        <div id="vendas-container">
            <div class="loading" style="color: #ffffff; text-align: center; padding: 2rem;">
                <div class="spinner"></div>
                <p>Sincronizando registros unificados...</p>
            </div>
        </div>
    </div>
`;

async function initVendasPage() {
    const container = document.getElementById('vendas-container');
    const totalCountEl = document.getElementById('vendas-total-count');
    const totalVolumeEl = document.getElementById('vendas-total-volume');
    
    try {
        // Chamada para o endpoint que agora lê a tabela unificada 'orders'
        const response = await fetch('/api/webhooks/mercadolivre/orders', {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        });

        if (!response.ok) throw new Error('Falha ao obter dados do servidor');
        const orders = await response.json();

        if (!orders || orders.length === 0) {
            container.innerHTML = `<div class="empty-state" style="color: #888; text-align: center; padding: 4rem;"><h3>Nenhum pedido registrado no banco.</h3></div>`;
            totalCountEl.textContent = "0";
            return;
        }

        let totalVolume = 0;
        totalCountEl.textContent = orders.length;

        container.innerHTML = orders.map(order => {
            const data = order.raw_data || {};
            const buyer = data.buyer || {};
            const amount = order.total_amount || 0;
            totalVolume += amount;

            // Define a cor baseada no marketplace (preparado para expansão)
            let brandColor = '#3b82f6'; // Default Blue
            let marketplaceName = (order.marketplace || 'MARKETPLACE').toUpperCase();
            
            if (order.marketplace === 'mercadolivre') {
                brandColor = '#fff159'; // Amarelo ML
            }

            const statusColor = order.status === 'paid' ? '#2ecc71' : '#f1c40f';

            return `
            <div class="product-result" style="background: #1a1c1e; border: 1px solid #333; border-left: 4px solid ${brandColor}; margin-bottom: 1rem; padding: 20px; border-radius: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <div>
                        <span style="font-size: 0.7rem; color: ${brandColor}; font-weight: 800; letter-spacing: 1px;">${marketplaceName}</span>
                        <h3 style="margin: 5px 0 0 0; color: #ffffff; font-size: 1.1rem;">Pedido #${data.id || order.external_id || '---'}</h3>
                    </div>
                    <span style="background: ${statusColor}; color: #000; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 800;">
                        ${(order.status || 'unknown').toUpperCase()}
                    </span>
                </div>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 1rem;">
                    <div>
                        <small style="color: #888; font-size: 0.7rem; text-transform: uppercase;">Comprador</small>
                        <div style="color: #ffffff; font-weight: 500;">${buyer.nickname || 'Cliente Final'}</div>
                    </div>
                    <div>
                        <small style="color: #888; font-size: 0.7rem; text-transform: uppercase;">Total do Pedido</small>
                        <div style="color: #2ecc71; font-weight: 700; font-size: 1.1rem;">
                            ${amount.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <small style="color: #888; font-size: 0.7rem; text-transform: uppercase;">Data de Registro</small>
                        <div style="color: #cccccc; font-size: 0.85rem;">${new Date(order.created_at).toLocaleString('pt-BR')}</div>
                    </div>
                </div>

                <details style="margin-top: 1.2rem; border-top: 1px solid #333; padding-top: 10px;">
                    <summary style="font-size: 0.75rem; color: #555; cursor: pointer; user-select: none;">Ver Detalhes Técnicos (JSON)</summary>
                    <pre style="background: #000; color: #0fa; padding: 10px; border-radius: 5px; font-size: 0.7rem; margin-top: 10px; overflow-x: auto;">${JSON.stringify(data, null, 2)}</pre>
                </details>
            </div>`;
        }).join('');

        totalVolumeEl.textContent = totalVolume.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

    } catch (error) {
        container.innerHTML = `<div style="color: #ff4d4d; padding: 20px;">Erro: ${error.message}</div>`;
    }
}