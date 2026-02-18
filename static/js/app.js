/**
 * BD | AS Platform - Main Application
 * Application initialization and global state management
 */

// Global Application State
const AppState = {
    batchProducts: [],
    productIdCounter: 1,
    resultCounter: 1,
    
    reset() {
        this.batchProducts = [];
        this.productIdCounter = 1;
        this.resultCounter = 1;
    }
};

// Page Templates
const HomeTemplate = () => `
    <div style="text-align: center; padding: 4rem 2rem;">
        <h1 style="font-size: 3rem; color: var(--text-primary); margin-bottom: 1rem;">👋 Bem-vindo ao BD | AS</h1>
        <p style="font-size: 1.25rem; color: var(--text-secondary); margin-bottom: 2rem;">Plataforma de Integração e Automação</p>
        <div style="max-width: 600px; margin: 0 auto; background: var(--bg-primary); padding: 2rem; border-radius: 16px; box-shadow: var(--shadow-md);">
            <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">Selecione uma opção no menu lateral para começar.</p>
            <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
                <a href="#/integracoes/sams" style="display: inline-flex; align-items: center; gap: 0.5rem; padding: 1rem 2rem; background: var(--primary-gradient); color: white; text-decoration: none; border-radius: 12px; font-weight: 600; transition: transform 0.2s;" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                    <span>🛒</span>
                    <span>Sam's Club</span>
                </a>
                <a href="#/integracoes/leroy" style="display: inline-flex; align-items: center; gap: 0.5rem; padding: 1rem 2rem; background: linear-gradient(135deg, #00A859 0%, #008046 100%); color: white; text-decoration: none; border-radius: 12px; font-weight: 600; transition: transform 0.2s;" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                    <span>🏠</span>
                    <span>Leroy Merlin</span>
                </a>
                <a href="#/integracoes/sodimac" style="display: inline-flex; align-items: center; gap: 0.5rem; padding: 1rem 2rem; background: linear-gradient(135deg, #FF6B35 0%, #E55A2B 100%); color: white; text-decoration: none; border-radius: 12px; font-weight: 600; transition: transform 0.2s;" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                    <span>🏪</span>
                    <span>Sodimac</span>
                </a>
            </div>
        </div>
    </div>
`;

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    // Proteção global: se não estiver logado, redireciona para /login
    const isLoginPage = window.location.pathname === '/login';
    const token = localStorage.getItem('access_token');
    if (!token && !isLoginPage) {
        window.location.href = '/login';
        return;
    }
    
    // Register routes
    router.addRoute('/', {
        title: 'Home',
        render: HomeTemplate
    });

    router.addRoute('/dashboard/ai-custos', {
        title: 'AI - Custos',
        render: DashboardTemplate,
        onMount: initDashboardPage
    });

    router.addRoute('/dashboard/vendas', {
        title: 'Painel de Vendas',
        render: VendasTemplate,      
        onMount: initVendasPage      
    });

    router.addRoute('/integracoes/sams', {
        title: "Integrações - Sam's Club",
        render: SamsClubTemplate,
        onMount: initSamsClubPage
    });

    router.addRoute('/integracoes/leroy', {
        title: 'Integrações - Leroy Merlin',
        render: LeroyMerlinTemplate,
        onMount: initLeroyMerlinPage
    });

    router.addRoute('/integracoes/sodimac', {
        title: 'Integrações - Sodimac',
        render: SodimacTemplate,
        onMount: initSodimacPage
    });

    // Initialize sidebar toggles
    router.initSidebarToggles();

    // Inject global confirm modal markup
    const modalHTML = `
        <div id="__confirm_modal_backdrop" class="confirm-modal-backdrop" aria-hidden="true">
            <div class="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="__confirm_modal_title">
                <h4 id="__confirm_modal_title">Confirmar Ação</h4>
                <p id="__confirm_modal_message">Tem certeza?</p>
                <div class="confirm-actions">
                    <button id="__confirm_modal_cancel" class="btn-modal-cancel">Cancelar</button>
                    <button id="__confirm_modal_confirm" class="btn-modal-confirm">Sim, continuar</button>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    const modalBackdrop = document.getElementById('__confirm_modal_backdrop');
    const modalMessage = document.getElementById('__confirm_modal_message');
    const modalConfirmBtn = document.getElementById('__confirm_modal_confirm');
    const modalCancelBtn = document.getElementById('__confirm_modal_cancel');

    let __confirmResolve = null;

    function showConfirmModal(message, options = {}) {
        modalMessage.textContent = message || 'Tem certeza?';
        modalBackdrop.classList.add('open');
        modalBackdrop.setAttribute('aria-hidden', 'false');

        return new Promise((resolve) => {
            __confirmResolve = resolve;
            setTimeout(() => modalConfirmBtn.focus(), 50);
        });
    }

    function hideConfirmModal() {
        modalBackdrop.classList.remove('open');
        modalBackdrop.setAttribute('aria-hidden', 'true');
    }

    modalConfirmBtn.addEventListener('click', () => {
        if (__confirmResolve) __confirmResolve(true);
        __confirmResolve = null;
        hideConfirmModal();
    });

    modalCancelBtn.addEventListener('click', () => {
        if (__confirmResolve) __confirmResolve(false);
        __confirmResolve = null;
        hideConfirmModal();
    });

    modalBackdrop.addEventListener('click', (e) => {
        if (e.target === modalBackdrop) {
            if (__confirmResolve) __confirmResolve(false);
            __confirmResolve = null;
            hideConfirmModal();
        }
    });

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modalBackdrop.classList.contains('open')) {
            if (__confirmResolve) __confirmResolve(false);
            __confirmResolve = null;
            hideConfirmModal();
        }
    });

    window.showConfirmModal = showConfirmModal;
    router.navigate();
});