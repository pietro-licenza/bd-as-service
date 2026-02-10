/**
 * BD | AS Platform - Sam's Club Integration
 * Image processing and batch analysis for Sam's Club products
 */

// Sam's Club Page Template
const SamsClubTemplate = () => `
    <div class="page-header">
        <h1>🛒 Processador de Imagens Sam's Club</h1>
        <p>Análise inteligente de produtos com IA para extração automática de informações</p>
    </div>

    <div class="upload-section">
        <h2>Processar Produtos</h2>
        <p>Adicione produtos e suas respectivas imagens. Nosso sistema de IA irá extrair automaticamente todas as informações relevantes.</p>
        
        <div id="productsContainer"></div>
        
        <div class="action-buttons">
            <button class="btn btn-add" id="addProductBtn">
                <span>➕</span>
                <span>Adicionar Produto</span>
            </button>
            <button class="btn btn-primary" id="processBatchBtn" style="display: none;">
                <span>🚀</span>
                <span>Processar Todos</span>
            </button>
            <button class="btn btn-secondary" id="clearBtn">
                <span>🗑️</span>
                <span>Limpar Resultados</span>
            </button>
        </div>
    </div>

    <div class="results-section">
        <h2>📊 Resultados</h2>
        <div id="results">
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>Nenhum resultado ainda. Adicione produtos e imagens para processar.</p>
            </div>
        </div>
    </div>
`;

// Sam's Club Page Initialization
function initSamsClubPage() {
    const addProductBtn = document.getElementById('addProductBtn');
    const processBatchBtn = document.getElementById('processBatchBtn');
    const clearBtn = document.getElementById('clearBtn');
    const productsContainer = document.getElementById('productsContainer');
    const resultsDiv = document.getElementById('results');

    // Reset state
    AppState.reset();

    // Initialize with one product
    addProduct();

    // Event Listeners
    addProductBtn.addEventListener('click', () => addProduct());
    processBatchBtn.addEventListener('click', () => processBatch());
    clearBtn.addEventListener('click', () => clearResults());

    // Helper Functions
    function addProduct() {
        const productId = AppState.productIdCounter++;
        const productDiv = document.createElement('div');
        productDiv.className = 'product-card';
        productDiv.id = `product-${productId}`;
        
        productDiv.innerHTML = `
            <h3>
                <span>📦 Produto #${productId}</span>
                <div class="product-header-actions">
                    <span class="file-count" id="count-${productId}">
                        <span>📸</span>
                        <span>0 imagens</span>
                    </span>
                    <button class="remove-btn" data-product-id="${productId}">
                        <span>❌</span>
                        <span>Remover</span>
                    </button>
                </div>
            </h3>
            <div class="file-input-wrapper">
                <label for="fileInput-${productId}" class="file-input-label">
                    <span>📁</span>
                    <span>Selecionar Imagens</span>
                </label>
                <input type="file" id="fileInput-${productId}" multiple accept="image/*">
            </div>
            <div class="selected-files" id="files-${productId}">
                <p style="color: var(--text-light); margin: 0;">Nenhuma imagem selecionada</p>
            </div>
        `;
        
        productsContainer.appendChild(productDiv);
        AppState.batchProducts.push({ id: productId, files: [] });
        
        // Add event listeners
        const input = document.getElementById(`fileInput-${productId}`);
        input.addEventListener('change', (e) => handleFileSelect(productId, e.target.files));

        const removeBtn = productDiv.querySelector('.remove-btn');
        removeBtn.addEventListener('click', () => removeProduct(productId));
        
        updateUI();
    }

    function removeProduct(productId) {
        const productDiv = document.getElementById(`product-${productId}`);
        if (productDiv) {
            productDiv.style.opacity = '0';
            productDiv.style.transform = 'scale(0.95)';
            setTimeout(() => {
                productDiv.remove();
            }, 200);
        }
        
        AppState.batchProducts = AppState.batchProducts.filter(p => p.id !== productId);
        updateUI();
    }

    function handleFileSelect(productId, files) {
        const product = AppState.batchProducts.find(p => p.id === productId);
        if (!product) return;
        
        product.files = Array.from(files);
        updateFileList(productId);
        updateUI();
    }

    function updateFileList(productId) {
        const product = AppState.batchProducts.find(p => p.id === productId);
        if (!product) return;
        
        const filesDiv = document.getElementById(`files-${productId}`);
        const countSpan = document.getElementById(`count-${productId}`);
        
        if (product.files.length === 0) {
            filesDiv.innerHTML = '<p style="color: var(--text-light); margin: 0;">Nenhuma imagem selecionada</p>';
            countSpan.innerHTML = '<span>📸</span><span>0 imagens</span>';
            return;
        }
        
        const fileList = product.files.map(file => 
            `<li>${file.name} <span style="color: var(--text-secondary);">(${(file.size / 1024).toFixed(1)} KB)</span></li>`
        ).join('');
        
        filesDiv.innerHTML = `<ul class="file-list">${fileList}</ul>`;
        countSpan.innerHTML = `<span>📸</span><span>${product.files.length} imagem(ns)</span>`;
    }

    function updateUI() {
        const totalFiles = AppState.batchProducts.reduce((sum, p) => sum + p.files.length, 0);
        processBatchBtn.style.display = totalFiles > 0 ? 'inline-flex' : 'none';
    }

    async function processBatch() {
        const productsWithFiles = AppState.batchProducts.filter(p => p.files.length > 0);
        if (productsWithFiles.length === 0) return;

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
            // Clear only previous results
            resultsDiv.innerHTML = '';
            AppState.resultCounter = 1;
        }

        processBatchBtn.disabled = true;
        processBatchBtn.innerHTML = '<span>⏳</span><span>Processando...</span>';

        const formData = new FormData();
        
        productsWithFiles.forEach((product, index) => {
            product.files.forEach((file, fileIndex) => {
                const newFile = new File(
                    [file], 
                    `product${index + 1}_img${fileIndex + 1}.${file.name.split('.').pop()}`, 
                    { type: file.type }
                );
                formData.append('files', newFile);
            });
        });

        try {
            showLoading();

            const response = await fetch('/api/sams-club/process-batch/', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            displayResults(data);

            // Clear products
            AppState.batchProducts = [];
            productsContainer.innerHTML = '';
            AppState.productIdCounter = 1;
            addProduct();
            updateUI();

        } catch (error) {
            console.error('Processing error:', error);
            displayError(error.message);
        } finally {
            processBatchBtn.disabled = false;
            processBatchBtn.innerHTML = '<span>🚀</span><span>Processar Todos</span>';
        }
    }

    function clearResults() {
        resultsDiv.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>Nenhum resultado ainda. Adicione produtos e imagens para processar.</p>
            </div>
        `;
        AppState.resultCounter = 1;
    }

    function showLoading() {
        const loadingHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <p class="loading-text">✨ Processando imagens com IA...</p>
                <p style="color: var(--text-secondary); font-size: 0.875rem; margin-top: 0.5rem;">
                    Isso pode levar alguns instantes
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
                </div>
            `;
            resultsDiv.insertAdjacentHTML('afterbegin', downloadHTML);
        }

        data.products.forEach(product => {
            let geminiData = product.gemini_response;
            
            if (!product.error) {
                try {
                    geminiData = JSON.parse(geminiData);
                } catch (e) {
                    // Keep as string if can't parse
                }
            }

            const isError = product.error !== undefined && product.error !== null;
            
            // Generated images HTML
            let generatedImagesHTML = '';
            if (product.generated_images_urls && product.generated_images_urls.length > 0) {
                const imageCards = product.generated_images_urls.map((url, idx) => `
                    <div style="flex: 1; min-width: 150px; max-width: 200px;">
                        <img src="${url}" alt="Imagem ${idx + 1}" style="width: 100%; border-radius: 8px; box-shadow: var(--shadow-sm); cursor: pointer;" onclick="window.open('${url}', '_blank')">
                        <p style="text-align: center; font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.5rem;">View ${idx + 1}</p>
                    </div>
                `).join('');
                
                generatedImagesHTML = `
                    <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border-color);">
                        <h4 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1rem;">
                            🖼️ Imagens Geradas (${product.generated_images_urls.length})
                        </h4>
                        <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                            ${imageCards}
                        </div>
                    </div>
                `;
            }
            
            const resultHTML = `
                <div class="product-result ${isError ? 'error' : ''}">
                    <h3>
                        <span>${isError ? '❌' : '✅'} Produto #${AppState.resultCounter++}</span>
                        <span class="badge">
                            <span>📸</span>
                            <span>${product.num_images} imagem(ns)</span>
                        </span>
                    </h3>
                    <div class="files-info">
                        📁 Arquivos: ${product.filenames.join(', ')}
                    </div>
                    <div class="product-data">
                        ${isError ? 
                            `<p style="color: var(--danger-color); font-weight: 500; margin: 0;"><strong>⚠️ Erro:</strong> ${product.error}</p>` :
                            `<pre>${JSON.stringify(geminiData, null, 2)}</pre>`
                        }
                        ${generatedImagesHTML}
                    </div>
                </div>
            `;

            resultsDiv.insertAdjacentHTML('afterbegin', resultHTML);
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
