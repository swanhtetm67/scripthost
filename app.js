const uploadForm = document.getElementById('uploadForm');

if (uploadForm) {
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(uploadForm);
        
        try {
            const res = await fetch('/upload', { method: 'POST', body: formData });
            const data = await res.json();
            if (res.ok) {
                showToast("Script Uploaded Successfully!");
                setTimeout(() => window.location.href = '/dashboard', 1500);
            } else {
                alert(data.detail);
            }
        } catch (err) {
            console.error(err);
        }
    });
}

async function loadScripts() {
    const grid = document.getElementById('scriptGrid');
    const res = await fetch('/api/scripts');
    const scripts = await res.json();

    grid.innerHTML = scripts.map(s => `
        <div class="glass-card p-6 rounded-xl border border-white/10 hover:border-blue-500/50 transition">
            <h3 class="font-bold text-lg mb-1">${s.title}</h3>
            <p class="text-xs text-slate-500 mb-4">ID: ${s.id} • v${s.latest_version} • ${s.views} views</p>
            
            <div class="flex flex-col gap-2">
                <button onclick="copyLoadstring('${s.id}')" class="bg-blue-600/20 text-blue-400 py-2 rounded-lg text-sm font-semibold hover:bg-blue-600 hover:text-white transition">
                    Copy Loadstring
                </button>
                <div class="flex gap-2">
                    <button onclick="deleteScript('${s.id}')" class="flex-1 bg-red-500/10 text-red-400 py-2 rounded-lg text-sm hover:bg-red-500 hover:text-white transition">
                        Delete
                    </button>
                    <a href="/raw/${s.id}" target="_blank" class="flex-1 bg-white/5 py-2 rounded-lg text-sm text-center hover:bg-white/10 transition">
                        View Raw
                    </a>
                </div>
            </div>
        </div>
    `).join('');
    lucide.createIcons();
}

function copyLoadstring(id) {
    const url = `${window.location.origin}/raw/${id}`;
    const code = `loadstring(game:HttpGet("${url}"))()`;
    navigator.clipboard.writeText(code);
    showToast("Loadstring copied to clipboard!");
}

async function deleteScript(id) {
    if (!confirm("Are you sure?")) return;
    await fetch(`/delete/${id}`, { method: 'POST' });
    loadScripts();
    showToast("Script deleted.");
}

function showToast(msg) {
    const toast = document.getElementById('toast');
    toast.innerText = msg;
    toast.classList.remove('translate-y-20', 'opacity-0');
    setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
    }, 3000);
}
