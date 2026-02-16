/**
 * BD | AS Platform - Sodimac Integration
 * Versão Completa: Visual Padronizado + Logs de Custo + Imagens HD + Download Excel
 */

// Sodimac Page Template
const SodimacTemplate = () => `
    <div class="page-header">
        <h1>🏢 Processador de Produtos Sodimac</h1>
        <p>Análise inteligente com redimensionamento de imagens HD e monitoramento de investimento real</p>
    </div>

    <div class="upload-section">
        <h2>Adicionar URLs de Produtos</h2>
        <p>Cole as URLs dos produtos da Sodimac. O sistema extrairá metadados, imagens em alta definição e gerará descrições profissionais.</p>
        
        <div class="url-input-section">
            <div class="textarea-wrapper">
                <label for="urlsTextarea">URLs dos Produtos (uma por linha)</label>
                <textarea 
                    id="urlsTextarea" 
                    placeholder="https://www.sodimac.com.br/sodimac-br/product/123456/produto-exemplo/123456/&#10;https://www.sodimac.com.br/sodimac-br/product/789012/outro-produto/789012/&#10;..."
                    rows="8"
                ></textarea>
                <div class="url-count" id="urlCount">0 URLs</div>
            </div>
        </div>
        
        <div class="action-buttons">
            <button class="btn btn-primary" id="processUrlsBtn" style="background: #FF6B35; border-color: #FF6B35;">
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
        <div id="downloadContainer"></div> <h2>📊 Resultados</h2>
        <div id="results">
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>Nenhum resultado ainda. Adicione URLs de produtos para processar.</p>
            </div>
        </div>
    </div>
`;

function initSodimacPage() {
    const urlsTextarea = document.getElementById('urlsTextarea');
    const urlCount = document.getElementById('urlCount');
    const processUrlsBtn = document.getElementById('processUrlsBtn');
    const clearUrlsBtn = document.getElementById('clearUrlsBtn');
    const resultsDiv = document.getElementById('results');
    const batchSummary = document.getElementById('batchSummary');
    const downloadContainer = document.getElementById('downloadContainer');

    // Reset state
    if (typeof AppState !== 'undefined') { AppState.reset(); }

    // Listener para contar URLs
    urlsTextarea.addEventListener('input', () => {
        const urls = getUrlsFromTextarea();
        urlCount.textContent = `${urls.length} URLs`;
        processUrlsBtn.disabled = urls.length === 0;
    });

    // Função para extrair URLs limpas
    function getUrlsFromTextarea() {
        const text = urlsTextarea.value.trim();
        if (!text) return [];
        return text.split('\n').map(url => url.trim()).filter(url => url.length > 0 && url.startsWith('http'));
    }

    // Botão Limpar
    clearUrlsBtn.addEventListener('click', () => {
        urlsTextarea.value = '';
        urlCount.textContent = '0 URLs';
        resultsDiv.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><p>Resultados limpos.</p></div>';
        batchSummary.innerHTML = '';
        downloadContainer.innerHTML = '';
        AppState.resultCounter = 1;
    });

    // Processamento Principal
    processUrlsBtn.addEventListener('click', async () => {
        const urls = getUrlsFromTextarea();
        if (urls.length === 0) return;

        // Confirmação se já houver resultados
        const hasResults = !resultsDiv.querySelector('.empty-state') && resultsDiv.children.length > 0;
        if (hasResults) {
            const confirmed = window.confirm('Deseja iniciar uma nova execução e apagar os resultados anteriores?');
            if (!confirmed) return;
        }

        processUrlsBtn.disabled = true;
        processUrlsBtn.innerHTML = '<span>⏳</span><span>Processando...</span>';
        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>✨ Processando produtos Sodimac com IA HD...</p></div>';
        downloadContainer.innerHTML = '';

        try {
            const response = await fetch('/api/sodimac/process-urls/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls })
            });

            if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
            const data = await response.json();
            
            // 1. Barra de Investimento (Laranja Sodimac)
            batchSummary.innerHTML = `
                <div style="background:#FF6B35; color:white; padding:1.2rem; border-radius:10px; display:flex; justify-content:space-between; align-items:center; box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                    <span>🎯 Lote Sodimac: <b>${data.total_products} itens</b></span>
                    <span>💰 Investimento Total: <b>${formatBRL(data.total_cost_batch_brl)}</b></span>
                </div>
            `;

            // 2. Botão de Download Excel
            if (data.excel_download_url) {
                downloadContainer.innerHTML = `
                    <div class="download-card" style="background:rgba(255,107,53,0.05); border:1px solid #FF6B35; padding:15px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
                        <span style="color:#FF6B35; font-weight:600;">📊 Relatório Sodimac gerado com sucesso!</span>
                        <a href="${data.excel_download_url}" download class="btn btn-primary" style="background:#FF6B35; border:none; padding:8px 20px; text-decoration:none; font-size:0.9rem; color:white; border-radius:5px;">⬇️ Baixar Excel</a>
                    </div>
                `;
            }

            // 3. Renderização dos Resultados
            resultsDiv.innerHTML = '';
            data.products.forEach(p => {
                const isError = !!p.error;
                const resultId = AppState.resultCounter++;

                // Lógica HD para imagens da Sodimac
                const hdImages = (p.image_urls || []).map(url => {
                    let cleanUrl = url.split(',')[0].trim();
                    return cleanUrl.replace(/w=(76|120)/, 'w=1036');
                });

                const resultHTML = `
                <div class="product-result ${isError ? 'error' : ''}" id="result-${resultId}">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1rem;">
                        <h3 style="margin:0; color:var(--text-primary);">${isError ? '❌' : '✅'} ${p.titulo || 'Erro'}</h3>
                        <span class="badge" style="background:rgba(255,107,53,0.1); color:#FF6B35;">Custo: ${formatBRL(p.total_cost_brl)}</span>
                    </div>

                    ${!isError ? `
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px; background:rgba(0,0,0,0.25); padding:14px; border-radius:8px; margin-bottom:1.5rem; font-size:0.85rem; border:1px solid rgba(255,255,255,0.05);">
                        <div style="border-right:1px solid #444; padding-right:10px;">
                            <small style="color:#888; display:block; margin-bottom:4px;">📥 INPUT (PROMPT + URL)</small>
                            <div style="display:flex; justify-content:space-between;">
                                <b>${p.input_tokens} tks</b>
                                <span style="color:#aaa;">${formatBRL(p.input_cost_brl)}</span>
                            </div>
                        </div>
                        <div style="padding-left:5px;">
                            <small style="color:#888; display:block; margin-bottom:4px;">📤 OUTPUT (IA + JSON)</small>
                            <div style="display:flex; justify-content:space-between;">
                                <b>${p.output_tokens} tks</b>
                                <span style="color:#aaa;">${formatBRL(p.output_cost_brl)}</span>
                            </div>
                        </div>
                    </div>` : ''}

                    <div class="product-data">
                        ${isError ? `<p style="color:#ef4444;">${p.error}</p>` : `
                            <p style="color:#FF6B35; font-size:1.8rem; font-weight:700; margin:0.5rem 0;">${p.preco}</p>
                            <div style="color:#ccc; line-height:1.7; margin-bottom:1.5rem; font-size:0.95rem; background:rgba(255,255,255,0.02); padding:15px; border-radius:8px;">
                                ${p.descricao.replace(/\n/g, '<br>')}
                            </div>
                            
                            <div style="display:flex; gap:12px; overflow-x:auto; padding-bottom:10px; scrollbar-width: thin;">
                                ${hdImages.map(img => `
                                    <img src="${img}" style="height:120px; border-radius:8px; border:1px solid #333; cursor:pointer;" 
                                         onclick="window.open('${img}')" title="Clique para ver em 1036px">
                                `).join('')}
                            </div>
                        `}
                    </div>
                </div>`;
                resultsDiv.insertAdjacentHTML('beforeend', resultHTML);
            });

            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });

        } catch (e) {
            resultsDiv.innerHTML = `<div class="product-result error"><h3>❌ Erro Crítico</h3><p>${e.message}</p></div>`;
        } finally {
            processUrlsBtn.disabled = false;
            processUrlsBtn.innerHTML = '<span>🚀</span><span>Processar URLs</span>';
        }
    });
}

// Funções globais de Toggle preservadas
function toggleResult(resultId) {
    const result = document.getElementById(`result-${resultId}`);
    if (result) {
        const content = result.querySelector('.product-data');
        if (content.style.display === 'none') {
            content.style.display = 'block';
        } else {
            content.style.display = 'none';
        }
    }
}