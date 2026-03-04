/**
 * static/js/router.js
 * SPA Router atualizado para suportar o módulo de Monitoramento
 */

class Router {
    constructor() {
        this.routes = new Map();
        this.currentRoute = null;
        this.appContent = document.getElementById('app-content');
        this.pageTitle = document.getElementById('page-title');
        
        window.addEventListener('hashchange', () => this.navigate());
        window.addEventListener('load', () => this.navigate());
    }

    /**
     * Registra uma rota com sua configuração
     */
    addRoute(path, config) {
        this.routes.set(path, config);
    }

    /**
     * Navega para a rota baseada no hash atual
     */
    navigate() {
        const token = localStorage.getItem('access_token');
        const isLoginPage = window.location.pathname === '/login';
        if (!token && !isLoginPage) {
            window.location.href = '/login';
            return;
        }

        const hash = window.location.hash.slice(1) || '/';
        const route = this.routes.get(hash) || this.routes.get('/');
        
        if (!route) {
            console.error('Nenhuma rota encontrada para:', hash);
            return;
        }

        this.updateNavigation(hash);
        this.pageTitle.textContent = route.title;
        this.appContent.innerHTML = route.render();
        
        if (route.onMount && typeof route.onMount === 'function') {
            route.onMount();
        }
        this.currentRoute = hash;
    }

    /**
     * Atualiza os estados ativos e expande menus automaticamente
     */
    updateNavigation(hash) {
        // Remove classes ativas de tudo
        document.querySelectorAll('.nav-link, .nav-subitem').forEach(el => {
            el.classList.remove('active');
        });

        if (hash === '/') {
            document.getElementById('nav-dashboard')?.classList.add('active');
        } else if (hash.startsWith('/integracoes/')) {
            const service = hash.split('/').pop();
            const navMap = {
                'sams': 'nav-sams-club',
                'leroy': 'nav-leroy-merlin',
                'sodimac': 'nav-sodimac',
                'decathlon': 'nav-decathlon',
                'outras': 'nav-other-integration'
            };
            document.getElementById(navMap[service])?.classList.add('active');
            this.expandSubmenu('nav-integrations');
        } else if (hash.startsWith('/dashboard/')) {
            const page = hash.split('/').pop();
            const navMap = {
                'ai-custos': 'nav-ai-custos',
                'vendas': 'nav-vendas-ml'
            };
            document.getElementById(navMap[page])?.classList.add('active');
            this.expandSubmenu('nav-dashboards-parent');
        } 
        // LÓGICA PARA MONITORAMENTO
        else if (hash === '/monitoramento/dashboard') {
            document.getElementById('nav-mon-dashboard')?.classList.add('active');
            this.expandSubmenu('nav-monitoring-parent');
        } else if (hash === '/monitoramento/config') {
            document.getElementById('nav-mon-config')?.classList.add('active');
            this.expandSubmenu('nav-monitoring-parent');
        }
    }

    /**
     * Força a abertura de um submenu
     */
    expandSubmenu(parentId) {
        const parentNav = document.getElementById(parentId);
        if (parentNav) {
            parentNav.classList.add('active', 'expanded');
            const submenu = parentNav.nextElementSibling;
            if (submenu && submenu.classList.contains('nav-submenu')) {
                submenu.classList.add('open');
            }
        }
    }

    /**
     * Inicializa os cliques para abrir/fechar menus
     */
    initSidebarToggles() {
        // LISTA ATUALIZADA COM O NOVO MENU
        const parentIds = ['nav-integrations', 'nav-dashboards-parent', 'nav-monitoring-parent'];
        
        parentIds.forEach(id => {
            const navElement = document.getElementById(id);
            if (navElement) {
                navElement.addEventListener('click', (e) => {
                    // Previne o comportamento padrão apenas se não for um link direto
                    if (!e.target.closest('a[href]')) {
                        e.preventDefault();
                    }
                    
                    const submenu = navElement.nextElementSibling;
                    if (submenu && submenu.classList.contains('nav-submenu')) {
                        const isOpen = submenu.classList.contains('open');
                        
                        if (isOpen) {
                            submenu.classList.remove('open');
                            navElement.classList.remove('expanded');
                        } else {
                            submenu.classList.add('open');
                            navElement.classList.add('expanded');
                        }
                    }
                });
            }
        });
    }
}

const router = new Router();