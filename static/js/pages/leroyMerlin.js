// Inicialização da página Leroy Merlin (placeholder)
function initLeroyMerlinPage() {}
/**
 * BD | AS Platform - Leroy Merlin Integration
 * URL-based product processing for Leroy Merlin
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
        <h2>📊 Resultados</h2>
        <div id="results">
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>Nenhum resultado ainda. Adicione URLs de produtos para processar.</p>
            </div>
        </div>
    </div>
`;

// Leroy Merlin Page Initialization
function initLeroyMerlinPage() {
    const urlsTextarea = document.getElementById('urlsTextarea');
    const urlCount = document.getElementById('urlCount');
    const processUrlsBtn = document.getElementById('processUrlsBtn');
    const clearUrlsBtn = document.getElementById('clearUrlsBtn');
    const resultsDiv = document.getElementById('results');

    // Reset state
    AppState.reset();

    // Event Listeners
    urlsTextarea.addEventListener('input', () => updateUrlCount());
    processUrlsBtn.addEventListener('click', () => processUrls());
    clearUrlsBtn.addEventListener('click', () => clearAll());

    // Helper Functions
    function updateUrlCount() {
        const urls = getUrlsFromTextarea();
        urlCount.textContent = `${urls.length} URLs`;
        processUrlsBtn.disabled = urls.length === 0;
    }

    function getUrlsFromTextarea() {
        const text = urlsTextarea.value.trim();
        if (!text) return [];
        
        return text
            .split('\n')
            .map(url => url.trim())
            .filter(url => url.length > 0 && url.startsWith('http'));
    }

    function clearAll() {
        urlsTextarea.value = '';
        updateUrlCount();
        resultsDiv.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>Nenhum resultado ainda. Adicione URLs de produtos para processar.</p>
            </div>
        `;
        AppState.resultCounter = 1;
    }

    // Clear only previous results (do not touch textarea)
    function clearPreviousResults() {
        resultsDiv.innerHTML = '';
        AppState.resultCounter = 1;
    }

    async function processUrls() {
        const urls = getUrlsFromTextarea();
        
        if (urls.length === 0) {
            alert('Por favor, adicione pelo menos uma URL válida');
            return;
        }

        // If there are existing results, ask user to confirm clearing them
        const hasResults = !resultsDiv.querySelector('.empty-state') && resultsDiv.children.length > 0;
        if (hasResults) {
            let confirmed = true;
            try {
                if (window.showConfirmModal) {
                    confirmed = await window.showConfirmModal('Já existem resultados na tela. Deseja iniciar uma nova execução e apagar os resultados anteriores?');
                } else {
                    confirmed = window.confirm('Já existem resultados na tela. Deseja iniciar uma nova execução e apagar os resultados anteriores?');
                }
            } catch (e) {
                console.error('Confirm modal error:', e);
                confirmed = window.confirm('Já existem resultados na tela. Deseja iniciar uma nova execução e apagar os resultados anteriores?');
            }

            if (!confirmed) return;
            // Clear only previous results (keep textarea until after request)
            clearPreviousResults();
        }

        processUrlsBtn.disabled = true;
        processUrlsBtn.innerHTML = '<span>⏳</span><span>Processando...</span>';

        try {
            showLoading(urls.length);

            const response = await fetch('/api/leroy-merlin/process-urls/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ urls })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            displayResults(data);

            // Clear textarea
            urlsTextarea.value = '';
            updateUrlCount();

        } catch (error) {
            console.error('Processing error:', error);
            displayError(error.message);
        } finally {
            processUrlsBtn.disabled = false;
            processUrlsBtn.innerHTML = '<span>🚀</span><span>Processar URLs</span>';
        }
    }

    function showLoading(count) {
        const loadingHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <p class="loading-text">✨ Processando ${count} produto(s) com IA...</p>
                <p style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 0.5rem;">
                    Extraindo imagens, análise de preços e geração de descrições
                </p>
                <p style="color: var(--text-light); font-size: 0.75rem; margin-top: 0.25rem;">
                    Isso pode levar alguns instantes...
                </p>
            </div>
        `;
        
        if (resultsDiv.querySelector('.empty-state')) {
            resultsDiv.innerHTML = loadingHTML;
        } else {
            resultsDiv.insertAdjacentHTML('afterbegin', loadingHTML);
        }
    }

    function displayResults(data) {
        const loading = resultsDiv.querySelector('.loading');
        const emptyState = resultsDiv.querySelector('.empty-state');
        if (loading) loading.remove();
        if (emptyState) emptyState.remove();

        // Add Excel download link if available
        if (data.excel_download_url) {
            const downloadHTML = `
                <div class="download-card">
                    <h3>
                        <span>📊</span>
                        <span>Relatório Excel Gerado com Sucesso!</span>
                    </h3>
                    <a href="${data.excel_download_url}" download class="download-link">
                        <span>⬇️</span>
                        <span>Download dos Resultados em Excel</span>
                    </a>
                    <p style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 0.5rem;">
                        ${data.total_products} produto(s) processado(s)
                    </p>
                </div>
            `;
            resultsDiv.insertAdjacentHTML('afterbegin', downloadHTML);
        }

        data.products.forEach((product, index) => {
            const isError = product.error !== undefined && product.error !== null;
            
            // Product images HTML
            let imagesHTML = '';
            if (product.image_urls && product.image_urls.length > 0) {
                const imageCards = product.image_urls.map((url, idx) => `
                    <div style="flex: 1; min-width: 150px; max-width: 200px;">
                        <img src="${url}" alt="Imagem ${idx + 1}" style="width: 100%; border-radius: 8px; box-shadow: var(--shadow-sm); cursor: pointer;" onclick="window.open('${url}', '_blank')">
                        <p style="text-align: center; font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">Imagem ${idx + 1}</p>
                    </div>
                `).join('');
                
                imagesHTML = `
                    <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border-color);">
                        <h4 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1rem;">
                            🖼️ Imagens do Produto (${product.image_urls.length})
                        </h4>
                        <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                            ${imageCards}
                        </div>
                    </div>
                `;
            }
            
            // Description HTML
            let descriptionHTML = '';
            if (product.descricao && product.descricao.trim().length > 0) {
                // Format description with line breaks
                const formattedDesc = product.descricao.split('\n').map(line => `<p style="margin: 0.5rem 0; color: var(--text-secondary); line-height: 1.6;">${line}</p>`).join('');
                descriptionHTML = `
                    <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border-color);">
                        <h4 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1rem;">
                            📋 Descrição do Produto
                        </h4>
                        <div style="color: var(--text-secondary);">
                            ${formattedDesc}
                        </div>
                    </div>
                `;
            }
            
            const resultHTML = `
                <div class="product-result ${isError ? 'error' : ''}">
                    <h3>
                        <span>${isError ? '❌' : '✅'} Produto #${AppState.resultCounter++}</span>
                        <span class="badge">
                            <span>🏠</span>
                            <span>Leroy Merlin</span>
                        </span>
                    </h3>
                    <div class="files-info">
                        🔗 URL: <a href="${product.url_original}" target="_blank" style="color: var(--primary-color);">${product.url_original}</a>
                    </div>
                    <div class="product-data">
                        ${isError ? 
                            `<p style="color: var(--danger-color); font-weight: 500; margin: 0;"><strong>⚠️ Erro:</strong> ${product.error}</p>` :
                            `
                            <div style="background: rgba(255, 255, 255, 0.05); padding: 1.25rem; border-radius: 8px;">
                                <h4 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1.125rem;">${product.titulo}</h4>
                                <p style="color: var(--success-color); font-size: 1.5rem; font-weight: 700; margin: 0.5rem 0;">${product.preco}</p>
                                ${product.marca ? `<p style="color: var(--text-secondary); margin: 0.5rem 0;"><strong>🏷️ Marca:</strong> ${product.marca}</p>` : ''}
                                ${product.ean ? `<p style="color: var(--text-secondary); margin: 0.5rem 0;"><strong>🔢 EAN:</strong> ${product.ean}</p>` : ''}
                                ${descriptionHTML}
                            </div>
                            ${imagesHTML}
                            `
                        }
                    </div>
                </div>
            `;

            resultsDiv.insertAdjacentHTML('beforeend', resultHTML);
        });
    }

    function displayError(message) {
        const loading = resultsDiv.querySelector('.loading');
        if (loading) loading.remove();

        const errorHTML = `
            <div class="product-result error">
                <h3>
                    <span>❌ Erro no Processamento</span>
                </h3>
                <div class="product-data">
                    <p style="color: var(--danger-color); font-weight: 500; margin: 0;">
                        <strong>⚠️ Erro:</strong> ${message}
                    </p>
                </div>
            </div>
        `;

        resultsDiv.insertAdjacentHTML('afterbegin', errorHTML);
    }
}
