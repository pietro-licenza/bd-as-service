// Inicialização da página Sodimac (placeholder)
function initSodimacPage() {}
/**
 * BD | AS Platform - Sodimac Integration
 * URL-based product processing for Sodimac
 */

// Sodimac Page Template
const SodimacTemplate = () => `
    <div class="page-header">
        <h1>🏢 Processador de Produtos Sodimac</h1>
        <p>Análise inteligente de produtos através de URLs para extração automática de informações</p>
    </div>

    <div class="upload-section">
        <h2>Adicionar URLs de Produtos</h2>
        <p>Cole as URLs dos produtos da Sodimac. Nosso sistema irá extrair imagens, título, preço, marca, EAN e gerar descrições profissionais.</p>

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

// Sodimac Page Initialization
function initSodimacPage() {
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
                <div class="empty-state-icon">No results</div>
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
        processUrlsBtn.innerHTML = '<span>Loading</span><span>Processando...</span>';

        try {
            showLoading(urls.length);

            const response = await fetch('/api/sodimac/process-urls/', {
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
            processUrlsBtn.innerHTML = '<span>Rocket</span><span>Processar URLs</span>';
        }
    }

    function showLoading(count) {
        const loadingHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <p class="loading-text">✨ Processando ${count} produto(s) com IA...</p>
                <p style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 0.5rem;">
                    Extraindo imagens, análise de preços, marcas, EAN e geração de descrições
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
                        ${data.total_products ? data.total_products + ' produto(s) processado(s)' : ''}
                    </p>
                </div>
            `;
            resultsDiv.insertAdjacentHTML('afterbegin', downloadHTML);
        }

        // Display individual product results
        data.products.forEach((product, index) => {
            const resultId = AppState.resultCounter++;
            const resultHTML = createProductResultHTML(product, resultId);
            resultsDiv.insertAdjacentHTML('beforeend', resultHTML);
        });

        // Scroll to results
        const firstResult = resultsDiv.querySelector('.product-result');
        if (firstResult) {
            firstResult.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    function displayError(message) {
        const loading = resultsDiv.querySelector('.loading');
        if (loading) loading.remove();

        const errorHTML = `
            <div class="error-message">
                <div class="error-icon">Error</div>
                <h3>Erro no Processamento</h3>
                <p>${message}</p>
                <button class="btn btn-secondary" onclick="this.parentElement.remove()">Fechar</button>
            </div>
        `;

        if (resultsDiv.querySelector('.empty-state')) {
            resultsDiv.innerHTML = errorHTML;
        } else {
            resultsDiv.insertAdjacentHTML('afterbegin', errorHTML);
        }
    }

    function createProductResultHTML(product, resultId) {
        const hasError = product.error;
        const hasDescription = product.descricao && product.descricao.trim().length > 0;

        let statusBadge = '';
        if (hasError) {
            statusBadge = '<span class="status-badge error">Erro</span>';
        } else if (hasDescription) {
            statusBadge = '<span class="status-badge success">Completo</span>';
        } else {
            statusBadge = '<span class="status-badge warning">Parcial</span>';
        }

        let imagesHTML = '';
        if (product.image_urls && product.image_urls.length > 0) {
            // Ajuste: cortar cada URL após a primeira vírgula e trocar w=76 por w=1036 se presente
            const cleanImageUrls = product.image_urls.map(url => {
                let cleanUrl = url;
                if (typeof cleanUrl === 'string' && cleanUrl.includes(',')) {
                    cleanUrl = cleanUrl.split(',')[0].trim();
                }
                // Se for uma imagem Sodimac com w=76 ou w=120, troca para w=1036
                if (typeof cleanUrl === 'string') {
                    cleanUrl = cleanUrl.replace(/w=(76|120)/, 'w=1036');
                }
                return cleanUrl;
            });
            const imageCards = cleanImageUrls.map((url, idx) => `
                <div style="flex: 1; min-width: 150px; max-width: 200px;">
                    <img src="${url}" alt="Imagem ${idx + 1}" style="width: 100%; border-radius: 8px; box-shadow: var(--shadow-sm); cursor: pointer;" onclick="window.open('${url}', '_blank')">
                    <p style="text-align: center; font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">Imagem ${idx + 1}</p>
                </div>
            `).join('');
            imagesHTML = `
                <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border-color);">
                    <h4 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1rem;">
                        🖼️ Imagens do Produto (${cleanImageUrls.length})
                    </h4>
                    <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                        ${imageCards}
                    </div>
                </div>
            `;
        } else {
            imagesHTML = '<div class="no-images">Nenhuma imagem encontrada</div>';
        }

        let descriptionHTML = '';
        if (hasDescription) {
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
        } else {
            descriptionHTML = '<div class="no-description">Descrição não gerada</div>';
        }

        const errorHTML = hasError
            ? `<div class="error-details"><strong>Erro:</strong> ${product.error}</div>`
            : '';

        return `
            <div class="product-result" id="result-${resultId}">
                <h3>
                    <span>✅ Produto #${resultId}</span>
                    <span class="badge">
                        <span>🏢</span>
                        <span>Sodimac</span>
                    </span>
                </h3>
                <div class="files-info">
                    🔗 URL: <a href="${product.url_original}" target="_blank" style="color: var(--primary-color);">${product.url_original}</a>
                </div>
                <div class="product-data">
                    <div style="background: rgba(255,255,255,0.05); padding: 1.25rem; border-radius: 8px;">
                        <h4 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1.125rem;">${product.titulo || 'N/A'}</h4>
                        <p style="color: var(--success-color); font-size: 1.5rem; font-weight: 700; margin: 0.5rem 0;">${product.preco || 'N/A'}</p>
                        ${product.marca ? `<p style=\"color: var(--text-secondary); margin: 0.5rem 0;\"><strong>🏷️ Marca:</strong> ${product.marca}</p>` : ''}
                        ${product.ean ? `<p style=\"color: var(--text-secondary); margin: 0.5rem 0;\"><strong>🔢 EAN:</strong> ${product.ean}</p>` : ''}
                        ${descriptionHTML}
                    </div>
                    ${imagesHTML}
                </div>
            </div>
        `;
    }

    // Initialize URL count
    updateUrlCount();
}

// Global function for toggling results
function toggleResult(resultId) {
    const result = document.getElementById(`result-${resultId}`);
    if (result) {
        const content = result.querySelector('.result-content');
        const toggleBtn = result.querySelector('.btn-icon span');

        if (content.style.display === 'none') {
            content.style.display = 'block';
            toggleBtn.textContent = 'Toggle';
        } else {
            content.style.display = 'none';
            toggleBtn.textContent = 'Toggle';
        }
    }
}
function toggleResult(resultId) {
    const result = document.getElementById(`result-${resultId}`);
    if (result) {
        const content = result.querySelector('.result-content');
        const toggleBtn = result.querySelector('.btn-icon .toggle-icon');

        if (content.style.display === 'none') {
            content.style.display = 'block';
            toggleBtn.textContent = '👁️';
        } else {
            content.style.display = 'none';
            toggleBtn.textContent = '➕';
        }
    }
}