/**
 * App - Main JavaScript utilities
 */

// HTMX configuration
document.addEventListener('DOMContentLoaded', function() {
    // Configure HTMX
    htmx.config.defaultSwapStyle = 'innerHTML';
    htmx.config.historyCacheSize = 10;

    // Add CSRF token to all HTMX requests if present
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    if (csrfToken) {
        document.body.addEventListener('htmx:configRequest', function(event) {
            event.detail.headers['X-CSRF-Token'] = csrfToken;
        });
    }

    // Add JWT token to all HTMX requests
    document.body.addEventListener('htmx:configRequest', function(event) {
        const token = localStorage.getItem('access_token');
        if (token) {
            event.detail.headers['Authorization'] = 'Bearer ' + token;
        }
    });

    // Handle HTMX errors
    document.body.addEventListener('htmx:responseError', function(event) {
        console.error('HTMX Error:', event.detail);
        showToast('An error occurred. Please try again.', 'error');
    });

    // Handle 401 responses (redirect to login)
    document.body.addEventListener('htmx:beforeOnLoad', function(event) {
        if (event.detail.xhr.status === 401) {
            localStorage.removeItem('access_token');
            window.location.href = '/login';
        }
    });
});

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Toast type (success, error, warning, info)
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-yellow-500',
        info: 'bg-blue-500'
    };

    toast.innerHTML = `
        <div class="flex items-center p-4 rounded-lg shadow-lg ${colors[type] || colors.info} text-white">
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-4 hover:opacity-75">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
            </button>
        </div>
    `;

    document.body.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Auto-remove after 5 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard', 'success');
    } catch (err) {
        console.error('Failed to copy:', err);
        showToast('Failed to copy', 'error');
    }
}

/**
 * Confirm action dialog
 * @param {string} message - Confirmation message
 * @returns {Promise<boolean>}
 */
function confirmAction(message) {
    return new Promise((resolve) => {
        const confirmed = window.confirm(message);
        resolve(confirmed);
    });
}

/**
 * Format genotype string with proper styling
 * @param {string} genotype - Raw genotype string
 * @returns {string} HTML formatted genotype
 */
function formatGenotype(genotype) {
    // Basic formatting - can be enhanced
    return genotype
        .replace(/\+/g, '<sup>+</sup>')
        .replace(/(\w+)\*/g, '<span class="gene">$1</span>*');
}

/**
 * Debounce function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function}
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Handle form submission with loading state
 * @param {HTMLFormElement} form - Form element
 * @param {Function} callback - Callback on success
 */
function handleFormSubmit(form, callback) {
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        submitBtn.disabled = true;
        submitBtn.innerHTML = '<svg class="spinner w-5 h-5" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Loading...';

        try {
            await callback(new FormData(form));
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    });
}

// Export functions for use in templates
window.App = {
    showToast,
    copyToClipboard,
    confirmAction,
    formatGenotype,
    debounce,
    handleFormSubmit
};
