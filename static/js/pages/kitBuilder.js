/**
 * BD | AS Platform - Kit Builder Integration
 * Suporta múltiplos kits independentes em paralelo.
 * v3: Multi-kit com múltiplas boxes
 */

const KitBuilderTemplate = () => `
    <div class="page-header">
        <h1>🎁 Kit Builder</h1>
        <p>Monte kits com produtos de múltiplos marketplaces. Defina o <strong>Produto Central</strong> e a <strong>quantidade</strong> de cada item.</p>
    </div>

    <div id="kitsContainer"></div>

    <div style="margin-top: 1rem; display: flex; justify-content: center;">
        <button class="btn btn-add" id="addKitBtn" style="padding: 12px 36px; font-size: 1rem; border: 2px dashed rgba(124,58,237,0.45); background: rgba(124,58,237,0.07); color: #c4b5fd; border-radius: 12px; cursor: pointer;">
            <span>➕</span>
            <span>Novo Kit</span>
        </button>
    </div>
`;

function initKitBuilderPage() {
    const kitsContainer = document.getElementById('kitsContainer');
    if (!kitsContainer) return;

    let kitCounter = 0;

    // ── Inicia com 1 kit box ──────────────────────────────────────────────────
    addKitBox();

    document.getElementById('addKitBtn').addEventListener('click', addKitBox);

    // ── Cria uma nova kit box ─────────────────────────────────────────────────
    function addKitBox() {
        const kitId = kitCounter++;

        const box = document.createElement('div');
        box.className = 'kit-box';
        box.id = `kit-box-${kitId}`;
        box.style.cssText = `
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(124,58,237,0.25);
            border-radius: 14px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        `;
        box.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; padding-bottom: 0.75rem; border-bottom: 1px solid rgba(124,58,237,0.3);">
                <h3 style="margin: 0; color: #c4b5fd; font-size: 1.1rem;">🎁 Kit ${kitId + 1}</h3>
                <button class="btn-remove-kit btn btn-secondary" data-kit="${kitId}" style="font-size: 0.8rem; padding: 4px 12px; display: none;" title="Remover este kit">
                    ✕ Remover Kit
                </button>
            </div>

            <p style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 0.75rem;">
                Suportamos <strong>Leroy Merlin</strong>, <strong>Sodimac</strong>, <strong>Decathlon</strong> e <strong>Sam's Club</strong>.
                Defina o <strong>Produto Central</strong> e a <strong>quantidade</strong> de cada item.
            </p>

            <div class="kit-urls-container" id="urls-${kitId}"></div>

            <div class="action-buttons" style="margin-top: 1rem;">
                <button class="btn btn-add add-url-btn" data-kit="${kitId}">
                    <span>➕</span><span>Adicionar Produto</span>
                </button>
                <button class="btn btn-primary process-kit-btn" data-kit="${kitId}" style="display: none; background: linear-gradient(135deg, #7C3AED 0%, #5B21B6 100%);">
                    <span>🚀</span><span>Montar Kit</span>
                </button>
                <button class="btn btn-secondary clear-kit-btn" data-kit="${kitId}">
                    <span>🗑️</span><span>Limpar</span>
                </button>
            </div>

            <div class="kit-result" id="result-${kitId}" style="margin-top: 1.25rem;"></div>
        `;

        kitsContainer.appendChild(box);

        // 2 inputs iniciais
        addUrlInput(kitId);
        addUrlInput(kitId);
        document.getElementById(`urls-${kitId}`).querySelector('.kit-central-radio').checked = true;

        // Eventos
        box.querySelector('.btn-remove-kit').addEventListener('click', () => removeKitBox(kitId));
        box.querySelector('.add-url-btn').addEventListener('click', () => addUrlInput(kitId));
        box.querySelector('.process-kit-btn').addEventListener('click', () => processKit(kitId));
        box.querySelector('.clear-kit-btn').addEventListener('click', () => clearKitBox(kitId));

        updateProcessBtn(kitId);
        updateRemoveButtons();
        box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // ── Remove uma kit box ────────────────────────────────────────────────────
    function removeKitBox(kitId) {
        const box = document.getElementById(`kit-box-${kitId}`);
        if (box) box.remove();
        updateRemoveButtons();
        if (kitsContainer.querySelectorAll('.kit-box').length === 0) addKitBox();
    }

    // ── Limpa os inputs e resultado de uma kit box ────────────────────────────
    function clearKitBox(kitId) {
        const urlsContainer = document.getElementById(`urls-${kitId}`);
        const resultDiv     = document.getElementById(`result-${kitId}`);
        if (urlsContainer) urlsContainer.innerHTML = '';
        if (resultDiv)     resultDiv.innerHTML     = '';
        addUrlInput(kitId);
        addUrlInput(kitId);
        const first = document.getElementById(`urls-${kitId}`).querySelector('.kit-central-radio');
        if (first) first.checked = true;
        updateProcessBtn(kitId);
    }

    // ── Mostra/oculta botão Remover (só aparece quando há 2+ kits) ────────────
    function updateRemoveButtons() {
        const boxes = kitsContainer.querySelectorAll('.kit-box');
        boxes.forEach(box => {
            const btn = box.querySelector('.btn-remove-kit');
            if (btn) btn.style.display = boxes.length > 1 ? 'inline-flex' : 'none';
        });
    }

    // ── Adiciona um input de URL dentro de uma kit box ────────────────────────
    function addUrlInput(kitId) {
        const urlsContainer = document.getElementById(`urls-${kitId}`);
        if (!urlsContainer) return;

        const count  = urlsContainer.querySelectorAll('.url-input-item').length;
        const urlDiv = document.createElement('div');
        urlDiv.className = 'url-input-item';
        urlDiv.innerHTML = `
            <div class="url-input-wrapper kit-url-row">
                <label class="kit-central-label" title="Marcar como Produto Central">
                    <input type="radio" name="produto_central_${kitId}" class="kit-central-radio" value="${count}" />
                    <span class="kit-central-text">⭐ Central</span>
                </label>
                <div class="kit-qty-wrapper">
                    <span class="kit-qty-label">Qtd</span>
                    <input type="number" class="kit-qty-input" value="1" min="1" max="999" />
                </div>
                <input type="url" class="kit-url-input"
                       placeholder="https://www.leroymerlin.com.br/... ou sodimac.com.br/..." />
                <button class="remove-url-btn">
                    <span>❌</span><span>Remover</span>
                </button>
            </div>
        `;
        urlsContainer.appendChild(urlDiv);

        urlDiv.querySelector('.kit-url-input').addEventListener('input', () => updateProcessBtn(kitId));
        urlDiv.querySelector('.remove-url-btn').addEventListener('click', () => {
            const wasChecked = urlDiv.querySelector('.kit-central-radio').checked;
            urlDiv.remove();
            if (wasChecked) {
                const first = document.getElementById(`urls-${kitId}`)?.querySelector('.kit-central-radio');
                if (first) first.checked = true;
            }
            updateProcessBtn(kitId);
        });
    }

    // ── Mostra/oculta o botão "Montar Kit" conforme URLs preenchidas ──────────
    function updateProcessBtn(kitId) {
        const urlsContainer = document.getElementById(`urls-${kitId}`);
        const processBtn    = document.querySelector(`.process-kit-btn[data-kit="${kitId}"]`);
        if (!urlsContainer || !processBtn) return;
        const validUrls = Array.from(urlsContainer.querySelectorAll('.kit-url-input'))
            .filter(i => i.value.trim().startsWith('http')).length;
        processBtn.style.display = validUrls >= 2 ? 'inline-flex' : 'none';
    }

    // ── Processa um kit (chama o endpoint) ────────────────────────────────────
    async function processKit(kitId) {
        const urlsContainer = document.getElementById(`urls-${kitId}`);
        const resultDiv     = document.getElementById(`result-${kitId}`);
        const processBtn    = document.querySelector(`.process-kit-btn[data-kit="${kitId}"]`);

        const rows  = Array.from(urlsContainer.querySelectorAll('.url-input-item'));
        const items = rows.map((row, rowIndex) => ({
            url:       row.querySelector('.kit-url-input').value.trim(),
            quantity:  parseInt(row.querySelector('.kit-qty-input').value) || 1,
            isCentral: row.querySelector('.kit-central-radio').checked,
            rowIndex
        })).filter(item => item.url.startsWith('http'));

        if (items.length < 2) {
            alert('Adicione pelo menos 2 URLs válidas para montar um kit.');
            return;
        }

        const urls                 = items.map(i => i.url);
        const quantities           = items.map(i => i.quantity);
        const centralIdx           = items.findIndex(i => i.isCentral);
        const produto_central_index = centralIdx >= 0 ? centralIdx : 0;

        processBtn.disabled = true;
        processBtn.innerHTML = '<span>⏳</span><span>Montando Kit...</span>';
        resultDiv.innerHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <p class="loading-text">Extraindo dados, gerando descrição e imagens com IA... (pode levar ~1 min)</p>
            </div>
        `;

        try {
            const response = await fetch('/api/kit-builder/process-urls/', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ urls, quantities, produto_central_index })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Erro HTTP: ${response.status}`);
            }

            const data = await response.json();
            displayKitResults(kitId, data);

        } catch (error) {
            console.error('Erro Kit Builder:', error);
            resultDiv.innerHTML = `
                <div class="product-result error">
                    <h3>❌ Erro ao montar kit</h3>
                    <p style="color: var(--danger-color);"><strong>Erro:</strong> ${error.message}</p>
                </div>
            `;
        } finally {
            processBtn.disabled = false;
            processBtn.innerHTML = '<span>🚀</span><span>Montar Kit</span>';
        }
    }

    // ── Exibe o resultado dentro da kit box ───────────────────────────────────
    function displayKitResults(kitId, data) {
        const resultDiv = document.getElementById(`result-${kitId}`);
        const kit       = data.kit;

        const imgCost  = kit.image_generation_cost_brl || 0;
        const textCost = (data.total_cost_batch_brl || 0) - imgCost;
        const dimsLine = [kit.largura_cm, kit.comprimento_cm, kit.altura_cm].filter(Boolean).join(' x ');

        // Labels das imagens: produtos individuais primeiro, depois kit
        const nIndividual = (kit.individual_product_urls || []).length;
        const imageLabels = [
            ...Array.from({ length: nIndividual }, (_, i) => `Produto ${i + 1} — Fundo Branco`),
            'Kit — Fundo Branco',
            'Kit — Lifestyle',
        ];

        const excelBtnId = `excel-btn-${kitId}`;

        resultDiv.innerHTML = `
            <!-- Resumo de custo -->
            <div style="background: linear-gradient(135deg, #7C3AED 0%, #5B21B6 100%); color: white; padding: 1rem 1.2rem; border-radius: 10px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 12px rgba(0,0,0,0.15); flex-wrap: wrap; gap: 8px; margin-bottom: 1rem;">
                <span>🎁 Kit montado com <b>${data.individual_products.length} produto(s)</b></span>
                <span style="display: flex; gap: 18px; flex-wrap: wrap;">
                    <span>📝 Texto: <b>${formatBRL(textCost)}</b></span>
                    <span>🖼️ Imagens: <b>${formatBRL(imgCost)}</b></span>
                    <span>💰 Total: <b>${formatBRL(data.total_cost_batch_brl)}</b></span>
                </span>
            </div>

            <!-- Excel -->
            ${data.excel_download_url ? `
                <div style="background: rgba(124,58,237,0.1); border: 1px solid #7C3AED; padding: 12px 15px; border-radius: 8px; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
                    <span style="color: #c4b5fd; font-weight: 600;">📊 Excel do kit pronto!</span>
                    <button id="${excelBtnId}" class="btn btn-primary" style="background: #7C3AED; padding: 7px 18px; font-size: 0.88rem; color: white; border-radius: 5px;">
                        ⬇️ Baixar Excel
                    </button>
                </div>
            ` : ''}

            <!-- Card do Kit -->
            <div class="product-result">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
                    <h3 style="margin: 0; color: var(--text-primary);">✅ ${kit.titulo || 'Kit sem título'}</h3>
                    <span class="badge" style="background: rgba(124,58,237,0.15); color: #c4b5fd; border-color: rgba(124,58,237,0.3);">🎁 Kit Builder</span>
                </div>

                <div style="display: flex; flex-direction: column; gap: 6px; background: rgba(30,30,30,0.18); border-radius: 8px; padding: 8px 18px; margin-bottom: 0.75rem;">
                    <span style="font-size: 1.1rem; color: var(--success-color); font-weight: 700;">Marca: ${kit.marca}</span>
                    ${dimsLine ? `<span style="color: var(--text-secondary);">📐 Dimensões (L x C x A): <b>${dimsLine} cm</b></span>` : ''}
                    ${kit.peso_kg ? `<span style="color: var(--text-secondary);">⚖️ Peso: <b>${kit.peso_kg} kg</b></span>` : ''}
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; background: rgba(0,0,0,0.25); padding: 14px; border-radius: 8px; margin-bottom: 1.5rem; font-size: 0.85rem; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="border-right: 1px solid #444; padding-right: 10px;">
                        <small style="color: #888; display: block; margin-bottom: 4px;">📥 INPUT</small>
                        <div style="color: #ede8e8; display: flex; justify-content: space-between;">
                            <b>${kit.input_tokens} tks</b>
                            <span style="color: #aaa;">${formatBRL(kit.input_cost_brl)}</span>
                        </div>
                    </div>
                    <div style="padding-left: 5px;">
                        <small style="color: #888; display: block; margin-bottom: 4px;">📤 OUTPUT</small>
                        <div style="color: #ede8e8; display: flex; justify-content: space-between;">
                            <b>${kit.output_tokens} tks</b>
                            <span style="color: #aaa;">${formatBRL(kit.output_cost_brl)}</span>
                        </div>
                    </div>
                </div>

                <div class="product-data">
                    <p style="color: var(--success-color); font-size: 1.8rem; font-weight: 700; margin-bottom: 1rem;">${kit.preco || ''}</p>

                    ${kit.generated_image_urls && kit.generated_image_urls.length > 0 ? `
                        <div style="margin-bottom: 1.5rem;">
                            <p style="font-weight: 600; color: #c4b5fd; font-size: 0.95rem; margin-bottom: 0.6rem;">✨ Imagens Geradas por IA</p>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px;">
                                ${kit.generated_image_urls.map((img, idx) => `
                                    <div style="position: relative; border-radius: 10px; overflow: hidden; border: 1px solid rgba(124,58,237,0.4); background: #111; cursor: pointer;" onclick="window.open('${img}')">
                                        <img src="${img}" style="width: 100%; aspect-ratio: 1; object-fit: cover; display: block; transition: transform 0.3s;"
                                             onmouseover="this.style.transform='scale(1.04)'"
                                             onmouseout="this.style.transform='scale(1)'">
                                        <div style="position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.65); padding: 5px 10px; font-size: 0.72rem; color: #e2e8f0; text-align: center;">
                                            ${imageLabels[idx] || `Foto ${idx + 1}`}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${kit.descricao ? `
                        <details open>
                            <summary style="cursor: pointer; font-weight: 600; color: var(--text-primary); margin-bottom: 0.75rem; font-size: 0.95rem;">Descrição do Kit</summary>
                            <div style="color: #ccc; line-height: 1.7; margin-top: 0.75rem; font-size: 0.95rem; background: rgba(255,255,255,0.02); padding: 15px; border-radius: 8px; white-space: pre-wrap;">${kit.descricao}</div>
                        </details>
                    ` : ''}

                    ${kit.image_urls && kit.image_urls.length > 0 ? `
                        <details style="margin-top: 1rem;">
                            <summary style="cursor: pointer; font-weight: 600; color: var(--text-secondary); font-size: 0.85rem;">
                                Fotos originais dos produtos (${kit.image_urls.length})
                            </summary>
                            <div style="display: flex; gap: 12px; overflow-x: auto; padding: 10px 0; scrollbar-width: thin; margin-top: 0.5rem;">
                                ${kit.image_urls.map(img => `
                                    <div style="flex-shrink: 0;">
                                        <img src="${img}" style="height: 100px; border-radius: 8px; border: 1px solid #333; cursor: pointer;" onclick="window.open('${img}')">
                                    </div>
                                `).join('')}
                            </div>
                        </details>
                    ` : ''}
                </div>
            </div>

            <!-- Produtos Individuais -->
            ${data.individual_products && data.individual_products.length > 0 ? `
                <div class="product-result" style="margin-top: 1rem;">
                    <h3>📦 Produtos que compõem o Kit</h3>
                    <div class="product-data">
                        ${data.individual_products.map((p, i) => {
                            const marketplaceName = (p.marketplace || '').replace('_', ' ').toUpperCase();
                            const centralBadge = p.is_produto_central
                                ? `<span style="background: rgba(124,58,237,0.2); color: #c4b5fd; border: 1px solid rgba(124,58,237,0.4); padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; margin-left: 8px;">⭐ CENTRAL</span>`
                                : '';
                            const qtyBadge = p.quantidade > 1
                                ? `<span style="background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; margin-left: 8px;">x${p.quantidade}</span>`
                                : '';
                            return `
                                <div style="padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);">
                                    <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin-bottom: 4px;">
                                        <strong style="color: var(--text-primary);">Produto ${i + 1} — ${marketplaceName}</strong>
                                        ${centralBadge}${qtyBadge}
                                    </div>
                                    ${p.error
                                        ? `<p style="color: var(--danger-color); margin-top: 4px;">Erro: ${p.error}</p>`
                                        : `<p style="margin: 4px 0; color: var(--text-secondary);">${p.titulo || 'Sem título'}</p>
                                           <p style="color: var(--success-color);">Unitário: ${p.preco || ''}
                                               ${p.quantidade > 1 ? `<span style="color: var(--text-light); font-size: 0.85rem;"> → Total (${p.quantidade}x): <b style="color: var(--success-color);">${p.preco_total || ''}</b></span>` : ''}
                                           </p>`
                                    }
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            ` : ''}
        `;

        // Bind botão Excel (precisa ser feito após innerHTML)
        const excelBtn = document.getElementById(excelBtnId);
        if (excelBtn) {
            excelBtn.addEventListener('click', async () => {
                excelBtn.disabled = true;
                excelBtn.textContent = '⏳ Gerando...';
                try {
                    const resp = await fetch('/api/kit-builder/generate-excel/', {
                        method:  'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body:    JSON.stringify({ kit })
                    });
                    if (!resp.ok) throw new Error('Erro ao gerar Excel');
                    const blob = await resp.blob();
                    const url  = window.URL.createObjectURL(blob);
                    const a    = document.createElement('a');
                    a.href = url;
                    a.download = `bhl_kit_${new Date().getTime()}.xlsx`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                } catch (e) {
                    alert('Erro ao gerar Excel: ' + e.message);
                } finally {
                    excelBtn.disabled = false;
                    excelBtn.textContent = '⬇️ Baixar Excel';
                }
            });
        }

        resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}
