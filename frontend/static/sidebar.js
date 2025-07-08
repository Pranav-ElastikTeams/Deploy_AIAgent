// Sidebar functionality
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebarOverlay');
const hamburger = document.getElementById('hamburger');
const navButtons = document.querySelectorAll('.nav-button');

let sidebarOpen = false;

function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
    if (sidebarOpen) {
        sidebar.classList.add('active');
        sidebarOverlay.classList.add('active');
        hamburger.classList.add('open');
        document.body.style.overflow = 'hidden';
    } else {
        sidebar.classList.remove('active');
        sidebarOverlay.classList.remove('active');
        hamburger.classList.remove('open');
        document.body.style.overflow = '';
    }
}

function closeSidebar() {
    if (sidebarOpen) {
        toggleSidebar();
    }
}

sidebarToggle.addEventListener('click', toggleSidebar);
sidebarOverlay.addEventListener('click', closeSidebar);
sidebar.addEventListener('click', (e) => { e.stopPropagation(); });
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebarOpen) {
        closeSidebar();
    }
});

// Highlight active nav button based on current path
function highlightActiveNav() {
    const path = window.location.pathname;
    navButtons.forEach(btn => btn.classList.remove('active'));
    document.getElementById('logComplaintBtn').classList.add('active');
}
highlightActiveNav();

// Function to load table data from backend
function loadTableData() {
    fetch('/api/cache_complaints')
        .then(response => response.json())
        .then(data => {
            console.log('Backend cache refreshed:', data);
        })
        .catch(err => {
            console.error('Failed to refresh backend cache:', err);
        });
}

// Add event listener to Inquire Complaint button
const inquireComplaintBtn = document.getElementById('inquireComplaintBtn');
if (inquireComplaintBtn) {
    inquireComplaintBtn.addEventListener('click', loadTableData);
} 