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
     * @param {string} path - Route path (e.g., '/', '/integracoes/sams')
     * @param {Object} config - Route configuration {title, render, onMount, navId}
     */
    addRoute(path, config) {
        this.routes.set(path, config);
    }

    /**
     * Navigate to the current hash route
     */
    navigate() {
        const hash = window.location.hash.slice(1) || '/';
        const route = this.routes.get(hash) || this.routes.get('/');
        
        if (!route) {
            console.error('No route found for:', hash);
            return;
        }

        // Update active navigation states
        this.updateNavigation(hash);
        
        // Update page content
        this.pageTitle.textContent = route.title;
        this.appContent.innerHTML = route.render();
        
        // Call onMount callback if exists
        if (route.onMount && typeof route.onMount === 'function') {
            route.onMount();
        }
        
        this.currentRoute = hash;
    }

    /**
     * Update navigation active states
     * @param {string} hash - Current route hash
     */
    updateNavigation(hash) {
        // Clear all active states
        document.querySelectorAll('.nav-link, .nav-subitem').forEach(el => {
            el.classList.remove('active');
        });

        // Set active based on route
        if (hash === '/') {
            document.getElementById('nav-dashboard')?.classList.add('active');
        } else if (hash === '/integracoes/sams') {
            document.getElementById('nav-sams-club')?.classList.add('active');
            this.expandIntegrations();
        } else if (hash === '/integracoes/leroy') {
            document.getElementById('nav-leroy-merlin')?.classList.add('active');
            this.expandIntegrations();
        } else if (hash === '/integracoes/outras') {
            document.getElementById('nav-other-integration')?.classList.add('active');
            this.expandIntegrations();
        }
    }

    /**
     * Expand the integrations submenu
     */
    expandIntegrations() {
        const integrationsNav = document.getElementById('nav-integrations');
        if (integrationsNav) {
            integrationsNav.classList.add('active', 'expanded');
            const submenu = integrationsNav.nextElementSibling;
            if (submenu) {
                submenu.classList.add('open');
            }
        }
    }

    /**
     * Initialize sidebar navigation toggles
     */
    initSidebarToggles() {
        const integrationsNav = document.getElementById('nav-integrations');
        if (integrationsNav) {
            integrationsNav.addEventListener('click', (e) => {
                if (!e.target.closest('a[href]')) {
                    e.preventDefault();
                    const submenu = integrationsNav.nextElementSibling;
                    
                    if (submenu.classList.contains('open')) {
                        submenu.classList.remove('open');
                        integrationsNav.classList.remove('expanded');
                    } else {
                        submenu.classList.add('open');
                        integrationsNav.classList.add('expanded');
                    }
                }
            });
        }
    }
}

// Export router instance
const router = new Router();
