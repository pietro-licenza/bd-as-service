// --- Globals & Utils ---
// Função para estimar custo Gemini
const PROMPT_TEXT = "You will receive 3 to 5 photos of a supermarket product. 1. Analyze the label photo(s) and extract: product name, price, and barcode. 2. Analyze the specification photo(s) and generate a professional marketplace description. 3. Among all photos, select the 'ideal product photo', meaning the clearest and sharpest front view. Return a JSON with the fields: 'nome', 'preco', 'codigo_barras', 'descricao', 'foto_ideal_index' (index of the ideal photo, starting at 1). If any field is not found, return empty for it.";
const PROMPT_LENGTH = PROMPT_TEXT.length; // Calculado dinamicamente
function estimateGeminiCost(promptLength, numImages, removeBackground) {
    const tokensPrompt = promptLength;
    const tokensImages = numImages * 1000;
    const tokensGeneration = removeBackground ? 2000 : 0; // Estimativa para remoção de fundo
    const totalTokens = tokensPrompt + tokensImages + tokensGeneration;
    const usd = (totalTokens / 1000000) * 0.50;
    const brl = usd * 5.0; // Cotação fixa
    return { tokens: totalTokens, usd: usd, brl: brl };
}

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
    if (typeof AppState !== 'undefined') {
        AppState.reset();
    }

    // Event Listeners
    addProductBtn.addEventListener('click', () => addProduct());
    processBatchBtn.addEventListener('click', () => processBatch());
    clearBtn.addEventListener('click', () => clearResults());

    // Initialize with one product
    addProduct();

    // --- Helper Functions Inside Init ---

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
            <div class="flag-checkbox-wrapper" style="margin-top: 1rem;">
                <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    <input type="checkbox" id="extractInfosFlag-${productId}" checked style="accent-color: var(--primary-color); width: 1.1rem; height: 1.1rem;">
                    <span style="color: var(--text-primary);">Extrair informações do produto</span>
                </label>
            </div>
            <div class="flag-checkbox-wrapper" style="margin-top: 1rem;">
                <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    <input type="checkbox" id="removeBackground-${productId}" style="accent-color: var(--primary-color); width: 1.1rem; height: 1.1rem;">
                    <span style="color: var(--text-primary);">Remover Fundo da Imagem</span>
                </label>
            </div>
            <div class="cost-estimate" id="costEstimate-${productId}" style="margin-top: 0.5rem; color: var(--text-secondary); font-size: 0.95rem;"></div>
            <div class="selected-files" id="files-${productId}">
                <p style="color: var(--text-light); margin: 0;">Nenhuma imagem selecionada</p>
            </div>
        `;
        
        productsContainer.appendChild(productDiv);
        AppState.batchProducts.push({ id: productId, files: [], extractInfos: true, removeBackground: false });

        const fileInput = document.getElementById(`fileInput-${productId}`);
        const removeBtn = productDiv.querySelector('.remove-btn');
        const extractInfosFlag = document.getElementById(`extractInfosFlag-${productId}`);
        const removeBackgroundFlag = document.getElementById(`removeBackground-${productId}`);
        
        // Eventos do Produto
        fileInput.addEventListener('change', (e) => {
            handleFileSelect(productId, e.target.files);
        });

        extractInfosFlag.addEventListener('change', (e) => {
            const product = AppState.batchProducts.find(p => p.id === productId);
            if (product) product.extractInfos = e.target.checked;
            updateCost(productId);
        });

        removeBackgroundFlag.addEventListener('change', (e) => {
            const product = AppState.batchProducts.find(p => p.id === productId);
            if (product) product.removeBackground = e.target.checked;
            updateCost(productId);
        });

        removeBtn.addEventListener('click', () => removeProduct(productId));
        updateCost(productId);
        updateCost(productId);
        updateUI();
    }

    function updateCost(productId) {
        const product = AppState.batchProducts.find(p => p.id === productId);
        const costDiv = document.getElementById(`costEstimate-${productId}`);
        if (!product || !costDiv) return;

        const promptLength = product.extractInfos ? PROMPT_LENGTH : 0;
        const estimate = estimateGeminiCost(promptLength, product.files.length, product.removeBackground);
        costDiv.innerHTML = `Estimativa: <b>${estimate.tokens}</b> tokens ≈ <b>US$ ${estimate.usd.toFixed(4)}</b> / <b>R$ ${estimate.brl.toFixed(2)}</b>`;
    }

    function removeProduct(productId) {
        const productDiv = document.getElementById(`product-${productId}`);
        if (productDiv) {
            productDiv.style.opacity = '0';
            productDiv.style.transform = 'scale(0.95)';
            setTimeout(() => {
                productDiv.remove();
                AppState.batchProducts = AppState.batchProducts.filter(p => p.id !== productId);
                updateUI();
            }, 200);
        }
    }

    function handleFileSelect(productId, files) {
        const product = AppState.batchProducts.find(p => p.id === productId);
        if (!product) return;
        
        product.files = Array.from(files);
        updateFileList(productId);
        updateCost(productId);
        updateUI();
    }

    function updateFileList(productId) {
        const product = AppState.batchProducts.find(p => p.id === productId);
        const filesDiv = document.getElementById(`files-${productId}`);
        const countSpan = document.getElementById(`count-${productId}`);
        if (!product || !filesDiv) return;
        
        if (product.files.length === 0) {
            filesDiv.innerHTML = '<p style="color: var(--text-light); margin: 0;">Nenhuma imagem selecionada</p>';
            countSpan.innerHTML = '<span>📸</span><span>0 imagens</span>';
        } else {
            const fileList = product.files.map(file => 
                `<li>${file.name} <span style="color: var(--text-secondary);">(${(file.size / 1024).toFixed(1)} KB)</span></li>`
            ).join('');
            filesDiv.innerHTML = `<ul class="file-list">${fileList}</ul>`;
            countSpan.innerHTML = `<span>📸</span><span>${product.files.length} imagem(ns)</span>`;
        }
    }

    function updateUI() {
        const totalFiles = AppState.batchProducts.reduce((sum, p) => sum + p.files.length, 0);
        processBatchBtn.style.display = totalFiles > 0 ? 'inline-flex' : 'none';
    }

    async function processBatch() {
        const productsWithFiles = AppState.batchProducts.filter(p => p.files.length > 0);
        if (productsWithFiles.length === 0) return;

        const hasResults = !resultsDiv.querySelector('.empty-state') && resultsDiv.children.length > 0;
        if (hasResults) {
            let confirmed = window.confirm('Já existem resultados na tela. Deseja iniciar uma nova execução e apagar os resultados anteriores?');
            if (!confirmed) return;
            resultsDiv.innerHTML = '';
            AppState.resultCounter = 1;
        }

        processBatchBtn.disabled = true;
        processBatchBtn.innerHTML = '<span>⏳</span><span>Processando...</span>';

        const formData = new FormData();
        productsWithFiles.forEach((product, index) => {
            formData.append(`extract_infos_${index + 1}`, product.extractInfos ? 'true' : 'false');
            formData.append(`remove_background_${index + 1}`, product.removeBackground ? 'true' : 'false');
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

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();
            displayResults(data);

            // Reset após sucesso
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
        // Show loading state
        resultsDiv.innerHTML = '<div class="loading" style="color: var(--text-primary);">Processando...</div>';
    }

    function displayResults(data) {
        // Clear loading
        const loading = resultsDiv.querySelector('.loading');
        if (loading) loading.remove();

        let products;
        if (Array.isArray(data)) {
            products = data;
        } else if (data && data.products) {
            products = data.products;
        } else {
            console.error('Invalid data format:', data);
            return;
        }

        products.forEach(product => {
            const isError = product.error;
            let generatedImagesHTML = '';
            if (product.generated_images_urls?.length > 0) {
                const imageCards = product.generated_images_urls.map((url, idx) => `
                    <div style="flex: 1; min-width: 150px; max-width: 200px;">
                        <img src="${url}" style="width: 100%; border-radius: 8px;" onclick="window.open('${url}', '_blank')">
                    </div>`).join('');
                generatedImagesHTML = `<div style="margin-top: 1rem;">${imageCards}</div>`;
            }
            
            const resultHTML = `
                <div class="product-result ${isError ? 'error' : ''}">
                    <h3>${isError ? '❌' : '✅'} Produto #${AppState.resultCounter++}</h3>
                    <div class="product-data">
                        ${isError ? 
                            `<p style="color: var(--danger-color); font-weight: 500; margin: 0;"><strong>⚠️ Erro:</strong> ${product.error}</p>` :
                            `
                            <div style="background: rgba(255, 255, 255, 0.05); padding: 1.25rem; border-radius: 8px;">
                                <h4 style="color: var(--text-primary); margin-bottom: 0.75rem; font-size: 1.125rem;">📊 Dados Extraídos</h4>
                                <pre style="color: var(--text-secondary); background: rgba(0, 0, 0, 0.2); padding: 1rem; border-radius: 6px; border: 1px solid var(--border-color); font-family: 'Courier New', monospace; font-size: 0.875rem; line-height: 1.4; margin: 0; white-space: pre-wrap; word-wrap: break-word;">${JSON.stringify(JSON.parse(product.gemini_response || '{}'), null, 2)}</pre>
                                ${generatedImagesHTML}
                            </div>
                            `
                        }
                    </div>
                </div>`;
            resultsDiv.insertAdjacentHTML('afterbegin', resultHTML);
        });
    }

    function displayError(message) {
        // Clear loading
        const loading = resultsDiv.querySelector('.loading');
        if (loading) loading.remove();

        resultsDiv.insertAdjacentHTML('afterbegin', `<div class="product-result error">
                <h3>❌ Erro no Processamento</h3>
                <div class="product-data">
                    <p style="color: var(--danger-color); font-weight: 500; margin: 0;"><strong>⚠️ Erro:</strong> ${message}</p>
                </div>
            </div>`);
    }
}