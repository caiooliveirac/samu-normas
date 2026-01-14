import { useCallback, useEffect, useRef, useState, useMemo } from 'react'

function getRulePreview(rule){
  const fromBody = (rule.body || '').trim()
  if (fromBody) return fromBody
  const firstBullet = rule.cards?.[0]?.bullets?.find(b => (b.text || '').trim())
  return (firstBullet?.text || '').trim()
}

function highlight(text, term){
  if (!term) return text
  const safe = term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')
  const re = new RegExp(`(${safe})`,'ig')
  const parts = String(text).split(re)
  if (parts.length === 1) return text
  return parts.map((p,i)=> re.test(p) ? <mark key={i} className="bg-brand-500/25 text-brand-800 font-medium rounded px-0.5">{p}</mark> : p )
}

export default function App(){
  const [rules, setRules] = useState([])
  const [expandedId, setExpandedId] = useState(null)
  const [isMobile, setIsMobile] = useState(false)
  const itemRefs = useRef(new Map())
  const buttonRefs = useRef(new Map())
  const contentRefs = useRef(new Map())
  const [heights, setHeights] = useState({})
  const [focusIndex, setFocusIndex] = useState(0)
  const [search, setSearch] = useState('')
  const [subtheme, setSubtheme] = useState('')
  const searchRef = useRef(null)
  const reportedTermsRef = useRef(new Set())

  // Fetch rules
  useEffect(()=>{
    fetch('/api/rules/')
      .then(r=>r.json())
      .then(json=>{
        const rs = json.results || []
        setRules(rs)
        if (matchMedia('(hover: none)').matches && rs.length){
          setExpandedId(rs[0].id)
        }
      })
      .catch(console.error)
  }, [])

  // Atalho '/'
  useEffect(()=>{
    const onKey = e => {
      if (e.key === '/'){
        if (document.activeElement && ['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) return
        e.preventDefault()
        searchRef.current?.focus()
      } else if (e.key === 'Escape') {
        setSearch('')
      }
    }
    window.addEventListener('keydown', onKey)
    return ()=> window.removeEventListener('keydown', onKey)
  }, [])

  // Detect mobile (hover:none)
  useEffect(()=>{
    const mq = matchMedia('(hover: none)')
    const update = () => setIsMobile(mq.matches)
    update()
    mq.addEventListener('change', update)
    return () => mq.removeEventListener('change', update)
  }, [])

  // Measure heights
  const measureHeights = useCallback(()=>{
    const next = {}
    for (const [id, el] of contentRefs.current.entries()){
      if (el) next[id] = el.scrollHeight
    }
    setHeights(next)
  }, [])

  useEffect(()=>{ measureHeights() }, [rules, measureHeights])

  // Mobile scroll central item auto-expand
  useEffect(()=>{
    if (!isMobile) return
    let ticking = false
    const onScroll = () => {
      if (ticking) return
      ticking = true
      requestAnimationFrame(()=>{
        ticking = false
        const center = window.innerHeight / 2
        let bestId = expandedId
        let bestDist = Infinity
        for (const [id, el] of itemRefs.current.entries()){
          if (!el) continue
          const r = el.getBoundingClientRect()
            const mid = r.top + r.height / 2
            const dist = Math.abs(mid - center)
            if (dist < bestDist){
              bestDist = dist
              bestId = id
            }
        }
        if (bestId !== expandedId) setExpandedId(bestId)
      })
    }
    window.addEventListener('scroll', onScroll, { passive:true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [isMobile, expandedId])

  const handleMouseEnter = (id) => {
    // Não expandir por hover no desktop: evita “paredão” ao passar o mouse.
    // Mantemos expansão por clique/teclado e por foco.
    void id
  }
  const handleFocus = (id, idx) => {
    setExpandedId(id)
    setFocusIndex(idx)
  }

  // Keyboard navigation (setas / home / end / enter / espaço)
  const handleKeyDown = (e, idx, rule) => {
    const display = filtered
    const total = display.length
    if (!['ArrowDown','ArrowUp','Home','End','Enter',' '].includes(e.key)) return
    e.preventDefault()
    if (e.key === 'ArrowDown') {
      const ni = Math.min(total - 1, idx + 1)
      setFocusIndex(ni)
      buttonRefs.current.get(display[ni].id)?.focus()
      setExpandedId(display[ni].id)
    } else if (e.key === 'ArrowUp') {
      const ni = Math.max(0, idx - 1)
      setFocusIndex(ni)
      buttonRefs.current.get(display[ni].id)?.focus()
      setExpandedId(display[ni].id)
    } else if (e.key === 'Home') {
      setFocusIndex(0)
      buttonRefs.current.get(display[0]?.id)?.focus()
      if (display[0]) setExpandedId(display[0].id)
    } else if (e.key === 'End') {
      const last = total - 1
      setFocusIndex(last)
      buttonRefs.current.get(display[last]?.id)?.focus()
      if (display[last]) setExpandedId(display[last].id)
    } else if (e.key === 'Enter' || e.key === ' ') {
      setExpandedId(rule.id)
    }
  }

  // Filtragem
  const filtered = useMemo(()=>{
    const t = search.trim().toLowerCase()
    const bySubtheme = subtheme ? rules.filter(r => String(r.id) === String(subtheme)) : rules
    if (!t) return bySubtheme
    return bySubtheme.filter(r => {
      if (r.title?.toLowerCase().includes(t)) return true
      if (r.category?.toLowerCase().includes(t)) return true
      if (r.cards?.some(c => c.bullets?.some(b => b.text?.toLowerCase().includes(t)))) return true
      if (r.body?.toLowerCase().includes(t)) return true
      return false
    })
  }, [rules, search, subtheme])

  // Se o usuário escolher um subtema, abre ele automaticamente
  useEffect(()=>{
    if (!subtheme) return
    const found = rules.find(r => String(r.id) === String(subtheme))
    if (found) setExpandedId(found.id)
  }, [subtheme, rules])

  useEffect(()=>{
    // Reset foco ao mudar filtro para manter dentro da lista
    if (focusIndex >= filtered.length) setFocusIndex(0)
  }, [filtered, focusIndex])

  const empty = filtered.length === 0
  const few = !empty && filtered.length < 3 && search.trim()
  const askHref = search.trim() ? `/ask/?q=${encodeURIComponent(search.trim())}` : '/ask/'

  // Log automático de termos sem resultado (>=3 chars) evitando envio repetido
  useEffect(()=>{
    const term = search.trim()
    if (!term || term.length < 3) return
    if (!empty) return
    if (reportedTermsRef.current.has(term.toLowerCase())) return
    reportedTermsRef.current.add(term.toLowerCase())
    const controller = new AbortController()
    fetch('/api/search-log/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ term, results_count: 0 }),
      signal: controller.signal
    }).catch(()=>{})
    return () => controller.abort()
  }, [empty, search])

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-10 font-sans">
      <header className="mb-6 flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-brand-600">Normas e Regras</h1>
            <p className="text-sm text-slate-600 mt-2">Consulte e, se não achar, envie sua dúvida para ampliar a base.</p>
            <p className="text-[11px] text-slate-500 mt-2">Atalhos: / busca · Esc limpa · ↑ ↓ navegam · Home/End · Enter/Espaço expandem.</p>
          </div>
          <a href={askHref} className="inline-flex items-center gap-2 rounded-lg bg-brand-500 hover:bg-brand-600 text-xs font-semibold px-4 py-2 shadow-sm shadow-brand-500/30 text-white transition-colors">
            <span>+ Perguntar</span>
          </a>
        </div>
        <div className="flex flex-col gap-2">
          <div className="relative">
            <input
              ref={searchRef}
              value={search}
              onChange={e=>setSearch(e.target.value)}
              placeholder="Buscar… (/ atalho)"
              aria-label="Buscar regras"
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 shadow-sm"
            />
            {search && (
              <button
                type="button"
                onClick={()=>setSearch('')}
                aria-label="Limpar busca"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
              >×</button>
            )}
          </div>
          {empty && search.trim() && (
            <div role="status" className="rounded-lg border border-slate-300/80 bg-slate-50 px-3 py-3 text-[13px] text-slate-600">
              Nenhuma regra encontrada para <strong className="text-brand-700">{search}</strong>.
              <a href={askHref} className="ml-1 text-brand-600 hover:text-brand-700 underline decoration-dotted">Enviar essa dúvida?</a>
            </div>
          )}
          {few && (
            <div className="text-[11px] text-slate-500">
              Poucos resultados. Se ainda está com dúvida,
              <a href={askHref} className="ml-1 text-brand-600 hover:text-brand-700 underline">pergunte</a>.
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="text-[11px] uppercase tracking-wide text-slate-500" htmlFor="subtheme">Subtema</label>
          <select
            id="subtheme"
            value={subtheme}
            onChange={(e)=>setSubtheme(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500 shadow-sm"
          >
            <option value="">Todos</option>
            {rules.map(r => (
              <option key={r.id} value={String(r.id)}>{r.title}</option>
            ))}
          </select>
          {subtheme && (
            <button
              type="button"
              onClick={()=>setSubtheme('')}
              className="text-xs text-slate-500 hover:text-slate-700 underline decoration-dotted"
            >Limpar</button>
          )}
        </div>
      </header>

      <ul className="flex flex-col gap-3" aria-label="Lista de regras" role="list">
        {empty && search.trim() && (
          <li className="text-sm text-slate-500 px-2 py-10 text-center border border-slate-300/80 rounded-xl bg-slate-50">Nenhuma regra corresponde à busca.</li>
        )}
        {filtered.map((rule, idx) => {
          const expanded = expandedId === rule.id
          const preview = getRulePreview(rule) || '(Sem conteúdo)'
          const measured = heights[rule.id] || 0
          const focused = idx === focusIndex
          return (
            <li
              key={rule.id}
              ref={el => itemRefs.current.set(rule.id, el)}
              className={`group relative rounded-xl border transition-colors duration-150 focus-within:ring-1 focus-within:ring-brand-400/50
                ${expanded ? 'border-brand-400/70 bg-brand-50 shadow-sm' : 'border-slate-300 bg-white hover:border-brand-300'}`}
              role="listitem"
            >
              <button
                ref={el => buttonRefs.current.set(rule.id, el)}
                type="button"
                className={`w-full text-left px-5 py-4 outline-none rounded-xl transition-colors duration-150
                  ${focused ? 'ring-2 ring-brand-400/70 ring-offset-2 ring-offset-white' : ''}`}
                aria-expanded={expanded}
                aria-controls={`rule-panel-${rule.id}`}
                onMouseEnter={()=>handleMouseEnter(rule.id)}
                onFocus={()=>handleFocus(rule.id, idx)}
                onKeyDown={(e)=>handleKeyDown(e, idx, rule)}
              >
                <div className="flex items-start gap-3">
                  <div className={`mt-1 h-2 w-2 rounded-full flex-shrink-0 transition-colors duration-150
                    ${expanded ? 'bg-brand-500 animate-pulse' : 'bg-slate-300 group-hover:bg-brand-400'}`}/>
                  <div className="flex-1 min-w-0">
                    <h2 className={`text-sm font-semibold tracking-wide transition-colors duration-150 line-clamp-1
                      ${expanded ? 'text-brand-600' : 'text-slate-700 group-hover:text-brand-600'}`}>{highlight(rule.title, search)}</h2>
                    <div className="flex flex-wrap gap-x-2 gap-y-1 mt-1 items-center text-[11px]">
                      {rule.category && (
                        <span className="uppercase tracking-wide text-slate-500">{highlight(rule.category, search)}</span>
                      )}
                      {search && !expanded && (
                        <span className="text-slate-400">•</span>
                      )}
                      {search && !expanded && (
                        <span className="text-[11px] text-slate-500 truncate max-w-[240px]">
                          {highlight(preview.slice(0, 120) + (preview.length>120?'…':''), search)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div
                  id={`rule-panel-${rule.id}`}
                  role="region"
                  aria-label={`Conteúdo da regra ${rule.title}`}
                  ref={el => contentRefs.current.set(rule.id, el)}
                  style={{ maxHeight: expanded ? measured : 0 }}
                  className="overflow-hidden transition-[max-height] duration-150 ease-out"
                >
                  <div className="pt-3 pl-[22px] pr-1">
                    {rule.body?.trim() && (
                      <div className={`text-[13px] leading-relaxed text-slate-600 transition-all duration-150
                        ${expanded ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-1'}`}
                      >
                        {String(rule.body).split(/\n{2,}/).map((p, i) => (
                          <p key={i} className={i ? 'mt-2' : ''}>{highlight(p, search)}</p>
                        ))}
                      </div>
                    )}

                    {rule.cards?.length > 0 && (
                      <div className="mt-3 grid grid-cols-1 gap-3">
                        {rule.cards.map((c) => (
                          <section
                            key={c.id}
                            className="rounded-lg border border-slate-200 bg-white/70 px-4 py-3"
                            aria-label={`Card ${c.title}`}
                          >
                            <h3 className="text-[12px] font-semibold text-slate-700">{highlight(c.title, search)}</h3>
                            <ul className="mt-2 flex flex-col gap-1">
                              {(c.bullets || []).map((b) => (
                                <li
                                  key={b.id}
                                  className="text-[12px] text-slate-600 pl-3 relative before:absolute before:left-0 before:top-2 before:h-1 before:w-1 before:rounded-full before:bg-brand-400/80"
                                >
                                  {highlight(b.text, search)}
                                </li>
                              ))}
                            </ul>
                          </section>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </button>
            </li>
          )
        })}
      </ul>

      {/* Botão flutuante permanente */}
      <a
        href={askHref}
        aria-label="Enviar nova pergunta"
        className="fixed bottom-5 right-5 inline-flex items-center gap-2 rounded-full bg-brand-500 hover:bg-brand-600 text-xs font-semibold px-5 py-3 shadow-lg shadow-brand-500/30 transition-colors group text-white"
      >
        <span className="h-2 w-2 rounded-full bg-white/70 group-hover:bg-white transition-colors"></span>
        <span>Perguntar</span>
      </a>
    </div>
  )
}
