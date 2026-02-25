/**
 * BD | AS Platform - Leroy Merlin Integration
 * Versão Completa: Visual Corrigido + Logs de Custo + Download Excel
 */

// Leroy Merlin Page Template
const LeroyMerlinTemplate = () => `
    <div class="page-header">
        <h1>🏠 Processador de Produtos Leroy Merlin</h1>
        <p>Análise inteligente de produtos através de URLs para extração automática de informações</p>
    </div>

    <div class="upload-section">
        <h2>Adicionar URLs de Produtos</h2>
        <p>Cole as URLs dos produtos da Leroy Merlin. Nosso sistema irá extrair imagens, título, preço e gerar descrições profissionais.</p>
        
        <div class="url-input-section">
            <div class="textarea-wrapper">
                <label for="urlsTextarea">URLs dos Produtos (uma por linha)</label>
                <textarea 
                    id="urlsTextarea" 
                    placeholder="https://www.leroymerlin.com.br/produto-exemplo_123456&#10;https://www.leroymerlin.com.br/outro-produto_789012&#10;..."
                    rows="8"
                ></textarea>
                <div class="url-count" id="urlCount">0 URLs</div>
            </div>
        </div>
        
        <div class="action-buttons">
            <button class="btn btn-primary" id="processUrlsBtn">
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

function initLeroyMerlinPage() {
    const urlsTextarea = document.getElementById('urlsTextarea');
    const urlCount = document.getElementById('urlCount');
    const processUrlsBtn = document.getElementById('processUrlsBtn');
    const clearUrlsBtn = document.getElementById('clearUrlsBtn');
    const resultsDiv = document.getElementById('results');
    const batchSummary = document.getElementById('batchSummary');
    const downloadContainer = document.getElementById('downloadContainer');

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
        resultsDiv.innerHTML = '<div class="loading"><div class="spinner"></div><p>✨ Analisando produtos e gerando relatório Excel...</p></div>';
        downloadContainer.innerHTML = ''; // Limpa download anterior

        try {
            const response = await fetch('/api/leroy-merlin/process-urls/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls })
            });

            if (!response.ok) throw new Error(`Erro HTTP: ${response.status}`);
            const data = await response.json();
            
            // 1. Renderização da Barra de Investimento
            batchSummary.innerHTML = `
                <div style="background:var(--primary-color); color:white; padding:1.2rem; border-radius:10px; display:flex; justify-content:space-between; align-items:center; box-shadow:0 4px 12px rgba(0,0,0,0.15);">
                    <span>🎯 Lote concluído: <b>${data.total_products} itens</b></span>
                    <span>💰 Investimento Total: <b>${formatBRL(data.total_cost_batch_brl)}</b></span>
                </div>
            `;

            // 2. Renderização do Botão de Download do Excel (Igual ao Sodimac)
            if (data.excel_download_url) {
                downloadContainer.innerHTML = `
                    <div class="download-card" style="background:rgba(0,168,89,0.1); border:1px solid #00A859; padding:15px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
                        <span style="color:#00A859; font-weight:600;">📊 Relatório Excel pronto para download!</span>
                        <button id="customExcelDownloadBtn" class="btn btn-primary" style="background:#00A859; padding:8px 20px; font-size:0.9rem; color: white; border-radius: 5px;">⬇️ Baixar Excel</button>
                    </div>
                `;
                // Adiciona lógica para download customizado
                setTimeout(() => {
                    const btn = document.getElementById('customExcelDownloadBtn');
                    if (btn) {
                        btn.addEventListener('click', async () => {
                            // Captura produtos com checkbox marcado
                            const checkboxes = document.querySelectorAll('.alterar-marca-checkbox');
                            const alterar_marca_urls = [];
                            checkboxes.forEach(cb => {
                                if (cb.checked) {
                                    alterar_marca_urls.push(cb.getAttribute('data-url'));
                                }
                            });
                            // Captura todos os produtos processados
                            const produtos = (window.leroyMerlinProducts || []);
                            btn.disabled = true;
                            btn.textContent = '⏳ Gerando Excel...';
                            try {
                                const resp = await fetch('/api/leroy-merlin/generate-excel/', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ produtos, alterar_marca_urls })
                                });
                                if (!resp.ok) throw new Error('Erro ao gerar Excel');
                                const blob = await resp.blob();
                                const url = window.URL.createObjectURL(blob);
                                const a = document.createElement('a');
                                a.href = url;
                                a.download = 'relatorio_leroy_merlin.xlsx';
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                                window.URL.revokeObjectURL(url);
                            } catch (e) {
                                alert('Erro ao gerar Excel: ' + e.message);
                            } finally {
                                btn.disabled = false;
                                btn.textContent = '⬇️ Baixar Excel';
                            }
                        });
                    }
                }, 100);
                        // Salva produtos processados para download
                        window.leroyMerlinProducts = data.products;
            }

            // 3. Renderização dos cards de produtos
            resultsDiv.innerHTML = data.products.map(p => {
                if (p.error) {
                    return `
                    <div class="product-result error">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <h3>❌ Erro no Processamento</h3>
                            <span class="badge" style="background:#ef4444; color:white;">Falha</span>
                        </div>
                        <p style="margin-top:10px;"><b>URL:</b> ${p.url_original}</p>
                        <p style="color:#ef4444;">${p.error}</p>
                    </div>`;
                }
                
                return `
                <div class="product-result">
                    <div style="display:flex; flex-direction:column; margin-bottom:1rem;">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <h3 style="margin:0; color:var(--text-primary);">✅ ${p.titulo}</h3>
                            <span class="badge" style="background:rgba(59,130,246,0.1); color:#3b82f6;">Investimento: ${formatBRL(p.total_cost_brl)}</span>
                        </div>
                        <div style="margin-top:0.7rem; display:flex; align-items:center; gap:18px; background:rgba(30,30,30,0.18); border-radius:8px; padding:8px 18px; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
                            <span style="font-size:1.3rem; color:var(--success-color); font-weight:700; letter-spacing:0.5px;">Marca: ${p.marca}</span>
                            <label style="display:flex; align-items:center; gap:12px; font-size:1.2rem; color:#3b82f6; font-weight:600;">
                                <input type="checkbox" class="alterar-marca-checkbox" data-url="${p.url_original}" style="width:28px; height:28px; border-radius:8px; box-shadow:0 1px 6px rgba(59,130,246,0.15); accent-color:#3b82f6;" />
                                <span style="font-size:1.2rem;">Alterar Marca</span>
                            </label>
                        </div>
                    </div>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:15px; background:rgba(0,0,0,0.25); padding:14px; border-radius:8px; margin-bottom:1.5rem; font-size:0.85rem; border:1px solid rgba(255,255,255,0.05);">
                        <div style="border-right:1px solid #444; padding-right:10px;">
                            <small style="color:#888; display:block; margin-bottom:4px;">📥 INPUT (PROMPT + URL)</small>
                            <div style="color:#ede8e8; display:flex; justify-content:space-between;">
                                <b>${p.input_tokens} tks</b>
                                <span style="color:#aaa;">${formatBRL(p.input_cost_brl)}</span>
                            </div>
                        </div>
                        <div style="padding-left:5px;">
                            <small style="color:#888; display:block; margin-bottom:4px;">📤 OUTPUT (IA + JSON)</small>
                            <div style="color:#ede8e8; display:flex; justify-content:space-between;">
                                <b>${p.output_tokens} tks</b>
                                <span style="color:#aaa;">${formatBRL(p.output_cost_brl)}</span>
                            </div>
                        </div>
                    </div>

                    <div class="product-data">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                            <p style="color:var(--success-color); font-size:1.8rem; font-weight:700; margin:0;">${p.preco}</p>
                            <small style="color:#666;">Original: <a href="${p.url_original}" target="_blank" style="color:#3b82f6;">Ver na Leroy</a></small>
                        </div>
                        <div style="color:#ccc; line-height:1.7; margin-bottom:1.5rem; font-size:0.95rem; background:rgba(255,255,255,0.02); padding:15px; border-radius:8px;">
                            ${p.descricao.replace(/\n/g, '<br>')}
                        </div>
                        <div style="display:flex; gap:12px; overflow-x:auto; padding-bottom:10px; scrollbar-width: thin;">
                            ${p.image_urls.map(img => `
                                <div class="image-wrapper" style="position:relative; flex-shrink:0;">
                                    <img src="${img}" style="height:120px; border-radius:8px; border:1px solid #333; transition:transform 0.2s; cursor:pointer;" 
                                         onclick="window.open('${img}')" 
                                         onmouseover="this.style.transform='scale(1.05)'" 
                                         onmouseout="this.style.transform='scale(1)'">
                                </div>
                            `).join('')}
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