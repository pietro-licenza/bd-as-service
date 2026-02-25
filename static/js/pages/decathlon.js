/**
 * BD | AS Platform - Decathlon Integration
 * Versão Final: Proteção contra erros + Layout Premium
 */

// Decathlon Page Template
const DecathlonTemplate = () => `
    <div class="page-header">
        <h1>🏸 Processador de Produtos Decathlon</h1>
        <p>Análise inteligente de produtos via URL com extração de EAN13 e geração de copy via IA.</p>
    </div>

    <div class="upload-section">
        <h2>Adicionar URLs de Produtos</h2>
        <p>Cole as URLs da Decathlon. Nosso sistema extrairá Título, Marca, EAN, Preço e gerará descrições profissionais.</p>
        
        <div class="url-input-section">
            <div class="textarea-wrapper">
                <label for="urlsTextarea">URLs dos Produtos (uma por linha)</label>
                <textarea 
                    id="urlsTextarea" 
                    placeholder="https://www.decathlon.com.br/produto-exemplo_123456&#10;https://www.decathlon.com.br/outro-produto_789012&#10;..."
                    rows="8"
                ></textarea>
                <div class="url-count" id="urlCount">0 URLs</div>
            </div>
        </div>
        
        <div class="action-buttons">
            <button class="btn btn-primary" id="processUrlsBtn" style="background-color: #0082C3; border-color: #0082C3;">
                <span>🚀</span>
                <span>Processar URLs</span>
            </button>
            <button class="btn btn-secondary" id="clearUrlsBtn">
                <span>🗑️</span>
                <span>Limpar</span>
            </button>
        </div>
    </div>

    <div class="results-section">
        <div id="batchSummary" style="margin-bottom: 1.5rem;"></div>
        <div id="downloadContainer"></div> 
        <h2>📊 Resultados</h2>
        <div id="results">
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>Nenhum resultado ainda. Adicione URLs de produtos para processar.</p>
            </div>
        </div>
    </div>
`;

function initDecathlonPage() {
    const urlsTextarea = document.getElementById('urlsTextarea');
    const urlCount = document.getElementById('urlCount');
    const processUrlsBtn = document.getElementById('processUrlsBtn');
    const clearUrlsBtn = document.getElementById('clearUrlsBtn');
    const resultsDiv = document.getElementById('results');
    const batchSummary = document.getElementById('batchSummary');
    const downloadContainer = document.getElementById('downloadContainer');

    // Reset de estado se necessário
    if (typeof AppState !== 'undefined') { AppState.reset(); }

    // Atualiza contador de URLs
    urlsTextarea.addEventListener('input', () => {
        const lines = urlsTextarea.value.trim().split('\n').filter(l => l.length > 10);
        urlCount.textContent = `${lines.length} URLs`;
    });

    // Limpa a tela
    clearUrlsBtn.addEventListener('click', () => {
        urlsTextarea.value = '';
        urlCount.textContent = '0 URLs';
        resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><p>Resultados limpos.</p></div>';
        batchSummary.innerHTML = '';
        downloadContainer.innerHTML = '';
    });

    // Processamento de URLs
    processUrlsBtn.addEventListener('click', async () => {
        const urls = urlsTextarea.value.trim().split('\n').filter(l => l.startsWith('http'));
        if (urls.length === 0) return;

        processUrlsBtn.disabled = true;
        processUrlsBtn.innerHTML = '<span>⏳</span><span>Processando...</span>';
        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>✨ Extraindo dados técnicos e consultando IA...</p></div>';
        downloadContainer.innerHTML = ''; 

        try {
            const response = await fetch('/api/decathlon/process-urls/', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                },
                body: JSON.stringify({ urls })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `Erro HTTP: ${response.status}`);
            }

            const data = await response.json();
            
            // 1. Renderização da Barra de Investimento
            batchSummary.innerHTML = `
                <div style="background:#0082C3; color:white; padding:1.2rem; border-radius:10px; display:flex; justify-content:space-between; align-items:center; box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                    <span>🎯 Lote concluído: <b>${data.total_products} itens</b></span>
                    <span>💰 Investimento Total: <b>${formatBRL(data.total_cost_batch_brl)}</b></span>
                </div>
            `;

            // 2. Botão de Download do Excel
            if (data.excel_download_url) {
                downloadContainer.innerHTML = `
                    <div class="download-card" style="background:rgba(0,130,195,0.1); border:1px solid #0082C3; padding:15px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
                        <span style="color:#0082C3; font-weight:600;">📊 Relatório Excel pronto para download!</span>
                        <a href="${data.excel_download_url}" download class="btn btn-primary" style="background:#0082C3; padding:8px 20px; text-decoration:none; font-size:0.9rem; color: white; border-radius: 5px;">⬇️ Baixar Excel</a>
                    </div>
                `;
            }

            // 3. Renderização dos cards de produtos
            if (!data.products || data.products.length === 0) {
                resultsDiv.innerHTML = '<p>Nenhum produto retornado.</p>';
                return;
            }

            resultsDiv.innerHTML = data.products.map(p => {
                // Caso o item venha com erro do Scraper/Backend
                if (p.error) {
                    return `
                    <div class="product-result error" style="border-left: 4px solid #ef4444;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h3>❌ Erro no Processamento</h3>
                            <span class="badge" style="background:#ef4444; color:white;">Falha</span>
                        </div>
                        <p style="margin-top:10px;"><b>URL:</b> ${p.url_original}</p>
                        <p style="color:#ef4444;">${p.error}</p>
                    </div>`;
                }
                
                // Proteção contra descrição nula
                const formattedDesc = p.descricao ? p.descricao.replace(/\n/g, '<br>') : "Descrição não disponível.";

                return `
                <div class="product-result">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1rem;">
                        <h3 style="margin:0; color:var(--text-primary);">✅ ${p.titulo}</h3>
                        <span class="badge" style="background:rgba(59,130,246,0.1); color:#3b82f6;">Investimento: ${formatBRL(p.total_cost_brl)}</span>
                    </div>

                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px; background:rgba(0,0,0,0.25); padding:14px; border-radius:8px; margin-bottom:1.5rem; font-size:0.85rem; border:1px solid rgba(255,255,255,0.05);">
                        <div style="border-right:1px solid #444; padding-right:10px;">
                            <small style="color:#888; display:block; margin-bottom:4px;">📥 INPUT (PROMPT + EAN)</small>
                            <div style="display:flex; justify-content:space-between;">
                                <b>${p.input_tokens || 0} tks</b>
                                <span style="color:#aaa;">${formatBRL(p.input_cost_brl || 0)}</span>
                            </div>
                        </div>
                        <div style="padding-left:5px;">
                            <small style="color:#888; display:block; margin-bottom:4px;">📤 OUTPUT (DESCRIÇÃO)</small>
                            <div style="display:flex; justify-content:space-between;">
                                <b>${p.output_tokens || 0} tks</b>
                                <span style="color:#aaa;">${formatBRL(p.output_cost_brl || 0)}</span>
                            </div>
                        </div>
                    </div>

                    <div class="product-data">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                            <p style="color:#0082C3; font-size:1.8rem; font-weight:700; margin:0;">${p.preco}</p>
                            <div style="text-align: right;">
                                <small style="color:#206d99; display: block;">EAN: ${p.ean || 'N/A'}</small>
                                <small style="color:#206d99; display: block;">Marca: ${p.marca || 'N/A'}</small>
                            </div>
                        </div>
                        
                        <div style="color:#ccc; line-height:1.7; margin-bottom:1.5rem; font-size:0.95rem; background:rgba(255,255,255,0.02); padding:15px; border-radius:8px;">
                            ${formattedDesc}
                        </div>
                        
                        <div style="display:flex; gap:12px; overflow-x:auto; padding-bottom:10px; scrollbar-width: thin;">
                            ${p.image_urls ? p.image_urls.map(img => `
                                <div class="image-wrapper" style="position:relative; flex-shrink:0;">
                                    <img src="${img}" style="height:120px; border-radius:8px; border:1px solid #333; transition:transform 0.2s; cursor:pointer;" 
                                         onclick="window.open('${img}')" 
                                         onmouseover="this.style.transform='scale(1.05)'" 
                                         onmouseout="this.style.transform='scale(1)'">
                                </div>
                            `).join('') : ''}
                        </div>
                    </div>
                </div>`;
            }).join('');

            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (e) {
            resultsDiv.innerHTML = `<div class="product-result error"><h3>❌ Erro Crítico</h3><p>${e.message}</p></div>`;
        } finally {
            processUrlsBtn.disabled = false;
            processUrlsBtn.innerHTML = '<span>🚀</span><span>Processar URLs</span>';
        }
    });
}