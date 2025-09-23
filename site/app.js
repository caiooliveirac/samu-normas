const state = { items: [], fuse: null };
const SYNONYMS = {
  "passagem de plantao": ["passagem de turno", "entrega de plantao", "troca de plantao"],
  "apoio policial": ["policia", "guarnição", "segurança pública", "pm"],
  "descanso": ["intervalo", "pausa", "revezamento"],
  "horario de chegada": ["pontualidade", "atraso", "inicio do plantao"],
  "troca de plantao": ["cobertura de plantao", "permuta"],
  "radio": ["comunicação", "conduta no rádio", "etiqueta no rádio"]
};
function normalize(s){ return s.normalize("NFD").replace(/\p{Diacritic}/gu,"").toLowerCase(); }
async function loadData() {
  const res = await fetch("./policies.json", { cache: "no-cache" });
  const data = await res.json();
  state.items = data;
  const options = { includeScore: true, threshold: 0.35, keys: ["titulo", "perguntas", "categoria", "perfil", "respostaPlain"] };
  state.items.forEach(it => { it.respostaPlain = (Array.isArray(it.resposta) ? it.resposta.join(" ") : it.resposta).replace(/<[^>]+>/g," "); });
  state.fuse = new Fuse(state.items, options);
  render(state.items);
}
function expandQuery(q){
  const base = normalize(q);
  const plus = [];
  Object.entries(SYNONYMS).forEach(([k, arr])=>{ if(base.includes(k)) plus.push(...arr); });
  return [q, ...plus].join(" ");
}
function handleSearch() {
  const q = document.getElementById("searchInput").value.trim();
  const categoria = document.getElementById("categoriaFilter").value;
  const perfil = document.getElementById("perfilFilter").value;
  let results = state.items;
  if (q) {
    const expanded = expandQuery(q);
    results = state.fuse.search(expanded).map(r => r.item);
  }
  if (categoria) results = results.filter(i => i.categoria === categoria);
  if (perfil)    results = results.filter(i => i.perfil.includes(perfil) || i.perfil.includes("Todos"));
  render(results);
}
function badge(text){ return `<span class="badge">${text}</span>`; }
function render(items){
  const el = document.getElementById("results");
  if (!items.length) {
    el.innerHTML = `<div class="card"><p>Nenhum resultado. Tente: <em>‘passagem de plantão’</em>, <em>‘apoio policial’</em>, <em>‘revezamento de descansos’</em>.</p></div>`;
    return;
  }
  el.innerHTML = items.map(i => `
    <article class="card">
      <h3>${i.titulo}</h3>
      <div class="meta">
        ${badge(i.categoria)}
        ${i.perfil.map(p => badge(p)).join(" ")}
        ${badge("Versão " + i.versao)}
        ${badge("Vigente desde " + i.vigencia_inicio)}
        ${i.vigencia_fim ? badge("Até " + i.vigencia_fim) : ""}
      </div>
      <div class="content">
        ${Array.isArray(i.resposta) ? `<ul>${i.resposta.map(b=>`<li>${b}</li>`).join("")}</ul>` : `<p>${i.resposta}</p>`}
        ${i.excecoes?.length ? `<p><strong>Exceções:</strong></p><ul>${i.excecoes.map(e=>`<li>${e}</li>`).join("")}</ul>` : ""}
        <p><small>Responsável: ${i.responsavel}${i.fonte_oficial ? ` — <a href="${i.fonte_oficial}" target="_blank" rel="noopener">Fonte oficial</a>` : ""}</small></p>
        <p><small>Última atualização: ${i.ultima_atualizacao}</small></p>
      </div>
    </article>
  `).join("");
}
document.addEventListener("DOMContentLoaded", () => {
  loadData();
  document.getElementById("searchInput").addEventListener("input", handleSearch);
  document.getElementById("categoriaFilter").addEventListener("change", handleSearch);
  document.getElementById("perfilFilter").addEventListener("change", handleSearch);
});
