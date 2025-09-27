import { useCallback, useEffect, useRef, useState, useMemo } from 'react'

function flattenRuleText(rule){
  const bulletTexts = rule.cards?.flatMap(c => c.bullets?.map(b => (b.text||'').trim()).filter(Boolean) || []) || []
  if (bulletTexts.length) return bulletTexts.join(' • ')
  return (rule.body || '').trim()
}

function highlight(text, term){
  if (!term) return text
  const safe = term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')
  const re = new RegExp(`(${safe})`,'ig')
  const parts = String(text).split(re)
  if (parts.length === 1) return text
  return parts.map((p,i)=> re.test(p) ? <mark key={i} className="bg-indigo-600/40 text-indigo-100 rounded px-0.5">{p}</mark> : p )
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
    if (isMobile) return
    setExpandedId(id)
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
    if (!t) return rules
    return rules.filter(r => {
      if (r.title?.toLowerCase().includes(t)) return true
      if (r.category?.toLowerCase().includes(t)) return true
      if (r.cards?.some(c => c.bullets?.some(b => b.text?.toLowerCase().includes(t)))) return true
      if (r.body?.toLowerCase().includes(t)) return true
      return false
    })
  }, [rules, search])

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
    <div className="mx-auto w-full max-w-3xl px-4 py-10 font-sans">
      <header className="mb-6 flex flex-col gap-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-100">Normas e Regras</h1>
            <p className="text-sm text-slate-400 mt-1">Consulte e, se não achar, envie sua dúvida para ampliar a base.</p>
            <p className="text-[11px] text-slate-500 mt-2">Atalhos: / busca · Esc limpa · ↑ ↓ navegam · Home/End · Enter/Espaço expandem.</p>
          </div>
          <a href={askHref} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold px-4 py-2 shadow-sm shadow-indigo-900/40 transition-colors">
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
              className="w-full rounded-lg border border-slate-600/60 bg-slate-900/60 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
            />
            {search && (
              <button
                type="button"
                onClick={()=>setSearch('')}
                aria-label="Limpar busca"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-200"
              >×</button>
            )}
          </div>
          {empty && search.trim() && (
            <div role="status" className="rounded-lg border border-slate-700/70 bg-slate-800/60 px-3 py-3 text-[13px] text-slate-300">
              Nenhuma regra encontrada para <strong className="text-slate-100">{search}</strong>.
              <a href={askHref} className="ml-1 text-indigo-400 hover:text-indigo-300 underline decoration-dotted">Enviar essa dúvida?</a>
            </div>
          )}
          {few && (
            <div className="text-[11px] text-slate-500">
              Poucos resultados. Se ainda está com dúvida,
              <a href={askHref} className="ml-1 text-indigo-400 hover:text-indigo-300 underline">pergunte</a>.
            </div>
          )}
        </div>
      </header>

      <ul className="flex flex-col gap-3" aria-label="Lista de regras" role="list">
        {empty && search.trim() && (
          <li className="text-sm text-slate-500 px-2 py-10 text-center border border-slate-700/50 rounded-xl bg-slate-800/30">Nenhuma regra corresponde à busca.</li>
        )}
        {filtered.map((rule, idx) => {
          const expanded = expandedId === rule.id
          const bodyRaw = flattenRuleText(rule) || '(Sem conteúdo)'
          const measured = heights[rule.id] || 0
          const focused = idx === focusIndex
          return (
            <li
              key={rule.id}
              ref={el => itemRefs.current.set(rule.id, el)}
              className={`group relative rounded-xl border transition-colors duration-150 backdrop-blur focus-within:ring-1 focus-within:ring-indigo-400/40
                ${expanded ? 'border-indigo-400/60 bg-slate-800/60 shadow-md shadow-indigo-500/5' : 'border-slate-700/60 bg-slate-800/30 hover:border-slate-500/70'}`}
              role="listitem"
            >
              <button
                ref={el => buttonRefs.current.set(rule.id, el)}
                type="button"
                className={`w-full text-left px-5 py-4 outline-none rounded-xl transition-colors duration-150
                  ${focused ? 'ring-2 ring-indigo-400/70 ring-offset-2 ring-offset-slate-900' : ''}`}
                aria-expanded={expanded}
                aria-controls={`rule-panel-${rule.id}`}
                onMouseEnter={()=>handleMouseEnter(rule.id)}
                onFocus={()=>handleFocus(rule.id, idx)}
                onKeyDown={(e)=>handleKeyDown(e, idx, rule)}
              >
                <div className="flex items-start gap-3">
                  <div className={`mt-1 h-2 w-2 rounded-full flex-shrink-0 transition-colors duration-150
                    ${expanded ? 'bg-indigo-400 animate-pulse' : 'bg-slate-500 group-hover:bg-indigo-300'}`}/>
                  <div className="flex-1 min-w-0">
                    <h2 className={`text-sm font-semibold tracking-wide transition-colors duration-150 line-clamp-1
                      ${expanded ? 'text-indigo-300' : 'text-slate-200 group-hover:text-slate-100'}`}>{highlight(rule.title, search)}</h2>
                    <div className="flex flex-wrap gap-x-2 gap-y-1 mt-1 items-center text-[11px]">
                      {rule.category && (
                        <span className="uppercase tracking-wide text-slate-500">{highlight(rule.category, search)}</span>
                      )}
                      {search && !expanded && (
                        <span className="text-slate-600">•</span>
                      )}
                      {search && !expanded && (
                        <span className="text-[11px] text-slate-500 truncate max-w-[220px]">
                          {highlight(bodyRaw.slice(0, 120) + (bodyRaw.length>120?'…':''), search)}
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
                    <p className={`text-[13px] leading-relaxed text-slate-300 transition-all duration-150
                      ${expanded ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-1'}`}>{highlight(bodyRaw, search)}</p>
                    {rule.cards?.length > 0 && (
                      <ul className="mt-3 flex flex-col gap-1">
                        {rule.cards.map(c => c.bullets.map(b => (
                          <li key={b.id} className="text-[12px] text-slate-400 pl-3 relative before:absolute before:left-0 before:top-2 before:h-1 before:w-1 before:rounded-full before:bg-slate-500">
                            {highlight(b.text, search)}
                          </li>
                        )))}
                      </ul>
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
        className="fixed bottom-5 right-5 inline-flex items-center gap-2 rounded-full bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold px-5 py-3 shadow-lg shadow-indigo-900/30 transition-colors group"
      >
        <span className="h-2 w-2 rounded-full bg-indigo-300 group-hover:bg-white transition-colors"></span>
        <span>Perguntar</span>
      </a>
    </div>
  )
}
