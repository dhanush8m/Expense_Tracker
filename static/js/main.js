// Vanilla JavaScript for ExpenseWise
document.addEventListener('DOMContentLoaded', function () {
    // 1. Light / Dark Mode Switch (visible on Dashboard, persisted across all pages)
    const themeSwitch = document.getElementById('theme-toggle-switch');
    const themeLabel = document.getElementById('theme-status-label');
    const rootEl = document.documentElement;

    function applyThemeFromStorage() {
        let savedTheme = 'light';
        try {
            savedTheme = localStorage.getItem('expensewise-theme') || 'light';
        } catch (e) {}

        const isDark = savedTheme === 'dark';
        rootEl.classList.toggle('dark', isDark);

        if (themeSwitch) {
            // Checked = Day / Sun (Light Mode); Unchecked = Night / Moon (Dark Mode)
            themeSwitch.checked = !isDark;
            themeSwitch.title = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
        }
        if (themeLabel) {
            themeLabel.textContent = isDark ? 'Dark Mode' : 'Light Mode';
        }
    }

    applyThemeFromStorage();

    if (themeSwitch) {
        themeSwitch.addEventListener('change', function () {
            const isDark = !themeSwitch.checked;
            rootEl.classList.toggle('dark', isDark);
            themeSwitch.title = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
            try {
                localStorage.setItem('expensewise-theme', isDark ? 'dark' : 'light');
            } catch (e) {}
            if (themeLabel) {
                themeLabel.textContent = isDark ? 'Dark Mode' : 'Light Mode';
            }
        });
    }

    // Re-sync theme and switch state when returning via browser back/forward cache
    window.addEventListener('pageshow', applyThemeFromStorage);

    // 2. Auto-dismiss alert notifications after 4 seconds
    const alerts = document.querySelectorAll('[data-flash-alert]');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(function () {
                alert.remove();
            }, 500);
        }, 4000);
    });
});
