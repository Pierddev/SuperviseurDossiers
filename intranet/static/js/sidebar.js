/**
 * Gestion de la sidebar (Navigation principale)
 * L'état est persisté via localStorage et appliqué via une classe sur l'élément <html>.
 * Toute la logique visuelle (largeurs, marges, visibilité) est gérée par le CSS 
 * dans layout.html via le sélecteur .sidebar-is-minimized.
 */
const buttonSidebar = document.getElementById("sidebar-toggle");

function toggleSidebar() {
    // On bascule la classe sur documentElement. Le CSS s'occupe du reste.
    const isMinimized = document.documentElement.classList.toggle("sidebar-is-minimized");
    localStorage.setItem("sidebarMinimized", isMinimized);
}

if (buttonSidebar) {
    buttonSidebar.addEventListener("click", toggleSidebar);
}
