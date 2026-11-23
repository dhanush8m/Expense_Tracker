// Vanilla JavaScript for ExpenseWise
document.addEventListener('DOMContentLoaded', function () {
    // Auto-dismiss alert notifications after 4 seconds
    const alerts = document.querySelectorAll('.bg-emerald-50, .bg-sky-50');
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
