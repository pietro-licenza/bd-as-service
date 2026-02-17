/**
 * BD | AS Platform - SPA Router
 * Client-side routing using hash-based navigation
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
     * Register a route with its configuration
     */
    addRoute(path, config) {
        this.routes.set(path, config);
    }

    /**
     * Navigate to the current hash route
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
            console.error('No route found for:', hash);
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
     * Update navigation active states
     */
    updateNavigation(hash) {
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
                'outras': 'nav-other-integration'
            };
            document.getElementById(navMap[service])?.classList.add('active');
            this.expandSubmenu('nav-integrations');
        } else if (hash === '/dashboard/ai-custos') {
            document.getElementById('nav-ai-custos')?.classList.add('active');
            this.expandSubmenu('nav-dashboards-parent');
        }
    }

    expandSubmenu(parentId) {
        const parentNav = document.getElementById(parentId);
        if (parentNav) {
            parentNav.classList.add('active', 'expanded');
            const submenu = parentNav.nextElementSibling;
            if (submenu) {
                submenu.classList.add('open');
            }
        }
    }

    initSidebarToggles() {
        const parentIds = ['nav-integrations', 'nav-dashboards-parent'];
        parentIds.forEach(id => {
            const navElement = document.getElementById(id);
            if (navElement) {
                navElement.addEventListener('click', (e) => {
                    if (!e.target.closest('a[href]')) {
                        e.preventDefault();
                        const submenu = navElement.nextElementSibling;
                        if (submenu.classList.contains('open')) {
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