// --- Globals & Utils ---

/**
 * Peso estimado em tokens do Prompt que reside no Backend (gemini_client.py).
 * Isso evita a duplicidade de texto e mantém a estimativa de custo precisa.
 */
const SYSTEM_PROMPT_WEIGHT = 350; 

// Função para formatar valores em Reais (BRL)
const formatBRL = (val) => {
    return (val || 0).toLocaleString('pt-BR', { 
        style: 'currency', 
        currency: 'BRL', 
        minimumFractionDigits: 4 
    });
};

/**
 * Estimativa visual antes do processamento (Pre-processamento)
 * @param {number} numImages - Quantidade de fotos selecionadas
 * @param {boolean} removeBackground - Se a flag de remoção de fundo está ativa
 */
function estimateGeminiCost(numImages, removeBackground) {
    const tokensPrompt = SYSTEM_PROMPT_WEIGHT;
    // Média de tokens para imagem redimensionada a 800px no Gemini 1.5/2.x
    const tokensImages = numImages * 258; 
    // Estimativa de tokens de saída para o JSON e possível remoção de fundo
    const tokensGeneration = removeBackground ? 1200 : 400; 
    
    const totalTokens = tokensPrompt + tokensImages + tokensGeneration;
    
    // Estimativa baseada nos preços do Gemini 2.5 Flash Lite
    const usd = (totalTokens / 1000000) * 0.075;
    const brl = usd * 5.10; // Cotação estimada
    
    return { tokens: totalTokens, brl: brl };
}

// Sam's Club Page Template
const SamsClubTemplate = () => `
    <div class="page-header">
        <h1>🛒 Processador de Imagens Sam's Club</h1>
        <p>Análise inteligente de produtos com IA para extração automática de informações</p>
    </div>

    <div class="upload-section">
        <h2>Processar Produtos</h2>
        <p>Adicione produtos e suas respectivas imagens. O sistema usará o prompt oficial do servidor para análise.</p>
        
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
        <div id="batchSummary" style="margin-bottom: 1.5rem;"></div>
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
    const batchSummary = document.getElementById('batchSummary');

    if (typeof AppState !== 'undefined') { AppState.reset(); }

    addProductBtn.addEventListener('click', () => addProduct());
    processBatchBtn.addEventListener('click', () => processBatch());
    clearBtn.addEventListener('click', () => clearResults());

    addProduct();

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
            <div class="flag-checkbox-wrapper" style="margin-top: 1rem; display: flex; flex-direction: column; gap: 0.5rem;">
                <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    <input type="checkbox" id="extractInfosFlag-${productId}" checked style="accent-color: var(--primary-color); width: 1.1rem; height: 1.1rem;">
                    <span style="color: var(--text-primary);">Extrair informações do produto</span>
                </label>
                <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    <input type="checkbox" id="removeBackground-${productId}" style="accent-color: var(--primary-color); width: 1.1rem; height: 1.1rem;">
                    <span style="color: var(--text-primary);">Remover Fundo da Imagem</span>
                </label>
            </div>
            <div class="cost-estimate" id="costEstimate-${productId}" style="margin-top: 0.8rem; padding: 0.5rem; background: rgba(255,255,255,0.03); border-radius: 4px; color: var(--text-secondary); font-size: 0.85rem; border-left: 3px solid var(--primary-color);"></div>
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
        
        fileInput.addEventListener('change', (e) => handleFileSelect(productId, e.target.files));
        extractInfosFlag.addEventListener('change', (e) => {
            const p = AppState.batchProducts.find(x => x.id === productId);
            if (p) p.extractInfos = e.target.checked;
            updateCost(productId);
        });
        removeBackgroundFlag.addEventListener('change', (e) => {
            const p = AppState.batchProducts.find(x => x.id === productId);
            if (p) p.removeBackground = e.target.checked;
            updateCost(productId);
        });
        removeBtn.addEventListener('click', () => removeProduct(productId));
        updateCost(productId);
        updateUI();
    }

    function updateCost(productId) {
        const product = AppState.batchProducts.find(p => p.id === productId);
        const costDiv = document.getElementById(`costEstimate-${productId}`);
        if (!product || !costDiv) return;

        // Se extractInfos estiver off, o prompt do sistema não é processado
        const currentPromptWeight = product.extractInfos ? SYSTEM_PROMPT_WEIGHT : 0;
        const estimate = estimateGeminiCost(product.files.length, product.removeBackground);
        
        costDiv.innerHTML = `<span>💡 Estimativa: <b>${estimate.tokens}</b> tokens ≈ <b style="color:var(--primary-color)">${formatBRL(estimate.brl)}</b></span>`;
    }

    function removeProduct(productId) {
        const productDiv = document.getElementById(`product-${productId}`);
        if (productDiv) {
            productDiv.remove();
            AppState.batchProducts = AppState.batchProducts.filter(p => p.id !== productId);
            updateUI();
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
            const fileList = product.files.map(file => `<li>${file.name}</li>`).join('');
            filesDiv.innerHTML = `<ul class="file-list">${fileList}</ul>`;
            countSpan.innerHTML = `<span>📸</span><span>${product.files.length} imagens</span>`;
        }
    }

    function updateUI() {
        const totalFiles = AppState.batchProducts.reduce((sum, p) => sum + p.files.length, 0);
        processBatchBtn.style.display = totalFiles > 0 ? 'inline-flex' : 'none';
    }

    async function processBatch() {
        const productsWithFiles = AppState.batchProducts.filter(p => p.files.length > 0);
        if (productsWithFiles.length === 0) return;

        resultsDiv.innerHTML = '<div class="loading">🚀 Processando Lote... Isso pode levar alguns segundos.</div>';
        processBatchBtn.disabled = true;

        const formData = new FormData();
        productsWithFiles.forEach((product, index) => {
            formData.append(`extract_infos_${index + 1}`, product.extractInfos);
            formData.append(`remove_background_${index + 1}`, product.removeBackground);
            product.files.forEach((file, fIdx) => {
                formData.append('files', new File([file], `product${index + 1}_img${fIdx + 1}.${file.name.split('.').pop()}`, { type: file.type }));
            });
        });

        try {
            const response = await fetch('/api/sams-club/process-batch/', { method: 'POST', body: formData });
            if (!response.ok) throw new Error(`Erro: ${response.status}`);
            const data = await response.json();
            displayResults(data);

            // Limpa formulário após sucesso para nova rodada
            productsContainer.innerHTML = '';
            AppState.batchProducts = [];
            AppState.productIdCounter = 1;
            addProduct();
            updateUI();

        } catch (error) {
            displayError(error.message);
        } finally {
            processBatchBtn.disabled = false;
        }
    }

    function displayResults(data) {
        resultsDiv.innerHTML = '';
        const products = data.products || [];
        
        // Calcular total real do lote (vindo do Backend)
        const batchTotalBRL = products.reduce((sum, p) => sum + (p.total_cost_brl || 0), 0);
        batchSummary.innerHTML = `
            <div style="background: var(--primary-color); color: white; padding: 1rem; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
                <span>🎯 Lote concluído: <b>${products.length} produtos</b></span>
                <span>💰 Investimento real: <b>${formatBRL(batchTotalBRL)}</b></span>
            </div>
        `;

        products.forEach(product => {
            const isError = product.error;
            let imagesHTML = '';
            if (product.generated_images_urls?.length > 0) {
                imagesHTML = `<div style="display:flex; gap:10px; margin-top:10px;">` + 
                    product.generated_images_urls.map(url => `<img src="${url}" style="width:120px; border-radius:4px; border:1px solid #444; cursor:pointer;" onclick="window.open('${url}')">`).join('') + 
                    `</div>`;
            }

            const resultHTML = `
                <div class="product-result ${isError ? 'error' : ''}">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                        <h3 style="margin:0;">${isError ? '❌' : '✅'} Produto: ${product.product_id}</h3>
                        <div style="text-align:right;">
                             <span class="badge bg-success" style="font-size:0.9rem;">Custo: ${formatBRL(product.total_cost_brl)}</span>
                        </div>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 1rem; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px;">
                        <div style="border-right: 1px solid #444; padding-right: 10px;">
                            <small style="color: #aaa; display:block; margin-bottom:4px;">📥 ENVIO (Prompt+Fotos)</small>
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span>${product.input_tokens} tokens</span>
                                <b style="color: #ddd;">${formatBRL(product.input_cost_brl)}</b>
                            </div>
                        </div>
                        <div style="padding-left: 5px;">
                            <small style="color: #aaa; display:block; margin-bottom:4px;">📤 RESPOSTA (Análise+JSON)</small>
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span>${product.output_tokens} tokens</span>
                                <b style="color: #ddd;">${formatBRL(product.output_cost_brl)}</b>
                            </div>
                        </div>
                    </div>

                    <div class="product-data">
                        ${isError ? 
                            `<p style="color: var(--danger-color)">${product.error}</p>` :
                            `<pre style="background:#111; padding:15px; border-radius:6px; color:#88f; font-size:0.85rem; overflow-x:auto;">${JSON.stringify(JSON.parse(product.gemini_response || '{}'), null, 2)}</pre>
                             ${imagesHTML}`
                        }
                    </div>
                </div>`;
            resultsDiv.insertAdjacentHTML('beforeend', resultHTML);
        });
    }

    function clearResults() {
        resultsDiv.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>Resultados limpos. Adicione novos produtos.</p>
            </div>
        `;
        batchSummary.innerHTML = '';
        AppState.resultCounter = 1;
    }

    function displayError(msg) {
        resultsDiv.innerHTML = `<div class="product-result error"><h3>❌ Erro Crítico</h3><p>${msg}</p></div>`;
    }
}