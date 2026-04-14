// ── Variables globales ──────────────────────────────────────────────────
let isDirty = false;

// ── Bandeau "modifications non sauvegardées" ────────────────────────────
function markDirty() {
    if (!isDirty) {
        isDirty = true;
        const banner = document.getElementById("unsaved-banner");
        if (banner) banner.classList.remove("hidden");
    }
}

function clearDirty() {
    isDirty = false;
    const banner = document.getElementById("unsaved-banner");
    if (banner) banner.classList.add("hidden");
}

// Écoute tous les inputs/selects/textareas du formulaire
const settingsForm = document.getElementById("settings-form");
if (settingsForm) {
    settingsForm.addEventListener("input", markDirty);
    settingsForm.addEventListener("change", markDirty);

    // Ne pas déclencher beforeunload lors de la soumission
    settingsForm.addEventListener("submit", clearDirty);
}

// Prévenir de quitter sans sauvegarder
window.addEventListener("beforeunload", (e) => {
    if (isDirty) {
        e.preventDefault();
        e.returnValue = "";
    }
});

// ── Section toggle (accordéon) ─────────────────────────────────────────
document.querySelectorAll(".section-toggle").forEach((btn) => {
    const section = btn.closest(".config-section");
    const body = section.querySelector(".section-body");
    const chevron = btn.querySelector(".chevron-icon");

    // Toutes ouvertes par défaut
    if (body) body.style.display = "block";
    if (chevron) chevron.style.transform = "rotate(180deg)";

    btn.addEventListener("click", (e) => {
        // Ne pas replier si on clique sur le bouton "Test connection" imbriqué
        if (e.target.closest(".test-conn-btn")) return;

        const open = body.style.display !== "none";
        body.style.display = open ? "none" : "block";
        if (chevron) chevron.style.transform = open ? "" : "rotate(180deg)";
    });
});

// ── Toggle mot de passe ───────────────────────────────────────────────
document.querySelectorAll(".toggle-pwd").forEach((btn) => {
    btn.addEventListener("click", () => {
        const input = btn.previousElementSibling;
        if (input) {
            input.type = input.type === "password" ? "text" : "password";
        }
    });
});

// ── Équivalent "minutes" du délai ────────────────────────────────────
function updateDelai() {
    const delaiInput = document.getElementById("delai-input");
    const delaiEquiv = document.getElementById("delai-equiv");

    if (delaiInput && delaiEquiv) {
        const v = parseInt(delaiInput.value) || 0;
        const m = (v / 60).toFixed(1);
        delaiEquiv.textContent = `Équivalent : ${m} minutes`;
    }
}

const delaiInput = document.getElementById("delai-input");
if (delaiInput) {
    delaiInput.addEventListener("input", updateDelai);
    updateDelai();
}

// ── Gestion des tags (chemins racines / exclus) ───────────────────────
function buildTagHtml(text, target) {
    const isExclus = target === "exclus";
    const colorBase = isExclus
        ? "bg-red-900/30 border-red-800/50 text-red-300"
        : "bg-primary-900/40 border-primary-800/60 text-primary-300";
    const closeColor = isExclus
        ? "text-red-500 hover:text-red-300"
        : "text-primary-500 hover:text-red-400";
    return `<span class="path-tag flex items-center gap-1.5 ${colorBase} text-xs font-mono px-2.5 py-1 rounded-lg border">
        ${text}
        <button type="button" class="remove-tag ${closeColor} transition-colors" data-target="${target}">
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
            </svg>
        </button>
    </span>`;
}

function syncHidden(target) {
    const container = document.getElementById(`${target}-tags`);
    const hiddenInput = document.getElementById(`${target}-hidden`);

    if (container && hiddenInput) {
        const tags = [...container.querySelectorAll(".path-tag")];
        const values = tags.map((t) => t.childNodes[0].textContent.trim());
        hiddenInput.value = values.join("\n");
    }
}

function addTag(target) {
    const input = document.getElementById(`${target}-input`);
    if (!input) return;

    const val = input.value.trim();
    if (!val) return;

    const container = document.getElementById(`${target}-tags`);
    if (!container) return;

    const span = document.createElement("div"); // div wrapper pour parser innerHTML
    span.innerHTML = buildTagHtml(val, target);
    container.appendChild(span.firstElementChild);

    input.value = "";
    syncHidden(target);
    markDirty();
}

// Enter sur les inputs de chemin ajoute le tag
["racines-input", "exclus-input"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            addTag(id === "racines-input" ? "racines" : "exclus");
        }
    });
});

// Délégation d'événements pour les boutons "×" des tags
["racines", "exclus"].forEach((target) => {
    const container = document.getElementById(`${target}-tags`);
    if (container) {
        container.addEventListener("click", (e) => {
            const btn = e.target.closest(".remove-tag");
            if (!btn) return;
            btn.closest(".path-tag").remove();
            syncHidden(target);
            markDirty();
        });
    }
});

// ── Seuils personnalisés : ajouter une ligne ──────────────────────────
// Rendu global pour le bouton 'onclick=addThresholdRow()' dans le HTML
window.addThresholdRow = function () {
    const pathInput = document.getElementById("new-seuil-path");
    const valInput = document.getElementById("new-seuil-val");

    if (!pathInput || !valInput) return;

    const path = pathInput.value.trim();
    const val = valInput.value.trim();
    if (!path || !val) return;

    const tbody = document.getElementById("seuils-tbody");
    const newRow = document.getElementById("new-seuil-row");

    if (!tbody || !newRow) return;

    const tr = document.createElement("tr");
    tr.className = "seuil-row";
    tr.innerHTML = `
        <td class="py-2 pr-4">
            <input type="text" name="custom_path[]" value="${path}"
                   class="config-input w-full bg-gray-800/60 border border-gray-700 rounded-lg text-gray-200 text-xs py-2 px-3 font-mono focus:outline-none focus:ring-1 focus:ring-primary-500 transition-all">
        </td>
        <td class="py-2 pr-4">
            <input type="number" name="custom_val[]" value="${val}" min="1"
                   class="config-input w-full bg-gray-800/60 border border-gray-700 rounded-lg text-gray-200 text-xs py-2 px-3 focus:outline-none focus:ring-1 focus:ring-primary-500 transition-all">
        </td>
        <td class="py-2">
            <button type="button" onclick="this.closest('.seuil-row').remove(); window.markDirtyGlobal();"
                    class="p-1.5 text-gray-600 hover:text-red-400 transition-colors">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
            </button>
        </td>
    `;
    tbody.insertBefore(tr, newRow);

    pathInput.value = "";
    valInput.value = "";
    markDirty();
};

// Expose markDirty to window so inline onclicks can find it before we remove inline onclicks
window.markDirtyGlobal = markDirty;

// ── Boutons Test connexion ─────────────────────────────────────────
function runTest(url, msgElId, data = null) {
    const el = document.getElementById(msgElId);
    if (!el) return;

    // margin-left spécifiquement pour le DB message car il est hors de la section paddée
    const marginClass = msgElId === "test-db-msg" ? "mx-6 " : "";

    el.className =
        `text-xs font-medium my-2 ${marginClass}text-gray-400 bg-gray-800/60 border border-gray-700 rounded-lg w-fit p-2`;
    el.textContent = "Connexion en cours…";
    el.classList.remove("hidden");

    const options = {
        method: "POST",
        headers: { "Content-Type": "application/json" },
    };
    if (data) options.body = JSON.stringify(data);

    fetch(url, options)
        .then((r) => r.json())
        .then((d) => {
            el.className = `text-xs font-medium my-2 ${marginClass}${d.ok ? "text-green-400 bg-green-800/20 border border-green-700" : "text-red-400 bg-red-800/20 border border-red-700"} rounded-lg w-fit p-2`;
            el.textContent = d.msg;
        })
        .catch(() => {
            el.className =
                `text-xs font-medium my-2 ${marginClass}text-red-400 bg-red-800/20 border border-red-700 rounded-lg w-fit p-2`;
            el.textContent = "Erreur réseau.";
        });
}

const btnTestDb = document.getElementById("btn-test-db");
if (btnTestDb) {
    btnTestDb.addEventListener("click", (e) => {
        e.stopPropagation();
        // Collecte les valeurs EN DIRECT du formulaire
        const payload = {
            host: document.getElementById("db_host")?.value || "",
            port: document.getElementById("db_port")?.value || "",
            user: document.getElementById("db_user")?.value || "",
            password: document.getElementById("db_password")?.value || "",
            name: document.getElementById("db_name")?.value || "",
        };
        runTest("/api/test-db", "test-db-msg", payload);
    });
}

const btnTestTeams = document.getElementById("btn-test-teams");
if (btnTestTeams) {
    btnTestTeams.addEventListener("click", () => {
        // Collecte l'URL du webhook EN DIRECT
        const payload = {
            webhook: document.getElementById("teams_webhook")?.value || "",
        };
        runTest("/api/test-teams", "test-teams-msg", payload);
    });
}

// ── Reset to defaults ────────────────────────────────────────────────
const btnReset = document.getElementById("btn-reset");
if (btnReset) {
    btnReset.addEventListener("click", () => {
        if (
            !confirm(
                "Réinitialiser tous les paramètres aux valeurs par défaut ? Cette action est irréversible.",
            )
        )
            return;
        // Redirige vers une route de reset (non implémentée — placeholder)
        alert("Fonctionnalité à venir.");
    });
}
