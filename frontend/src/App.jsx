import { useCallback, useEffect, useRef, useState, useMemo } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'framer-motion'

const ATTACHMENTS = [
  { id: 'anexo-01', title: 'Anexo 1', href: '/anexos/anexo-01.jpeg' },
  { id: 'anexo-02', title: 'Anexo 2', href: '/anexos/anexo-02.jpeg' },
  { id: 'anexo-03', title: 'Anexo 3', href: '/anexos/anexo-03.jpeg' },
  { id: 'anexo-04', title: 'Anexo 4', href: '/anexos/anexo-04.jpeg' },
  { id: 'anexo-05', title: 'Anexo 5', href: '/anexos/anexo-05.jpeg' },
]

function getRulePreview(rule){
  const fromBody = (rule.body || '').trim()
  if (fromBody) return fromBody
  const firstBullet = rule.cards?.[0]?.bullets?.find(b => (b.text || '').trim())
  return (firstBullet?.text || '').trim()
}

function getExcerptAroundTerm(text, term, { before = 320, after = 480 } = {}){
  const hay = String(text || '')
  const needle = String(term || '').trim().toLowerCase()
  if (!hay || !needle) return ''
  const idx = hay.toLowerCase().indexOf(needle)
  if (idx < 0) return ''

  const start = Math.max(0, idx - before)
  const end = Math.min(hay.length, idx + needle.length + after)
  let out = hay.slice(start, end).trim()
  // Garantia extra: o recorte sempre deve conter o termo.
  // (Ajuda a evitar casos em que o fallback não mostra a palavra.)
  if (!out.toLowerCase().includes(needle)) {
    out = hay.slice(idx, Math.min(hay.length, idx + needle.length + after)).trim()
  }
  if (start > 0) out = `…${out}`
  if (end < hay.length) out = `${out}…`
  return out
}

function getRuleSearchExcerpt(rule, term){
  if (!term) return ''

  // Prioridade: corpo > bullets > títulos de cards > categoria/título.
  const fromBody = getExcerptAroundTerm(rule.body, term)
  if (fromBody) return fromBody

  for (const c of (rule.cards || [])){
    for (const b of (c.bullets || [])){
      const fromBullet = getExcerptAroundTerm(b.text, term)
      if (fromBullet) return fromBullet
    }
  }

  for (const c of (rule.cards || [])){
    const fromCardTitle = getExcerptAroundTerm(c.title, term, { before: 32, after: 64 })
    if (fromCardTitle) return fromCardTitle
  }

  const fromCategory = getExcerptAroundTerm(rule.category, term, { before: 24, after: 64 })
  if (fromCategory) return fromCategory
  const fromTitle = getExcerptAroundTerm(rule.title, term, { before: 24, after: 64 })
  if (fromTitle) return fromTitle

  return ''
}

function getExcerptsAroundTermAll(text, term, { before = 220, after = 320, max = 10 } = {}){
  const hay = String(text || '')
  const needleRaw = String(term || '').trim()
  const needle = needleRaw.toLowerCase()
  if (!hay || !needle) return []

  const hayLower = hay.toLowerCase()
  const indices = []
  let from = 0
  while (indices.length < 80) {
    const idx = hayLower.indexOf(needle, from)
    if (idx < 0) break
    indices.push(idx)
    from = idx + Math.max(1, needle.length)
  }
  if (!indices.length) return []

  // Converte índices em janelas e mescla sobreposições (para não repetir o mesmo trecho).
  const windows = indices
    .map(idx => ({
      idx,
      start: Math.max(0, idx - before),
      end: Math.min(hay.length, idx + needle.length + after),
    }))
    .sort((a, b) => a.start - b.start)

  const merged = []
  for (const w of windows) {
    const last = merged[merged.length - 1]
    if (!last || w.start > last.end - Math.floor(before / 2)) {
      merged.push({ ...w })
    } else {
      last.end = Math.max(last.end, w.end)
    }
  }

  const out = []
  for (const w of merged) {
    if (out.length >= max) break
    let snippet = hay.slice(w.start, w.end).trim()
    if (!snippet.toLowerCase().includes(needle)) {
      // Garantia: inclui o termo.
      snippet = hay.slice(w.idx, Math.min(hay.length, w.idx + needle.length + after)).trim()
    }
    if (w.start > 0) snippet = `…${snippet}`
    if (w.end < hay.length) snippet = `${snippet}…`
    out.push(snippet)
  }

  // Dedupe simples
  return Array.from(new Set(out))
}

function getRuleSearchExcerpts(rule, term){
  if (!term) return []

  // Corpo: pode ter várias ocorrências.
  const fromBody = getExcerptsAroundTermAll(rule.body, term, { before: 240, after: 360, max: 10 })
  if (fromBody.length) return fromBody

  // Bullets: agrega até 10 ocorrências (prioriza os primeiros matches)
  const out = []
  for (const c of (rule.cards || [])){
    for (const b of (c.bullets || [])){
      const snippets = getExcerptsAroundTermAll(b.text, term, { before: 220, after: 340, max: 1 })
      for (const s of snippets) {
        out.push(s)
        if (out.length >= 10) return Array.from(new Set(out))
      }
    }
  }

  // Fallback: single excerpt.
  const single = getRuleSearchExcerpt(rule, term)
  return single ? [single] : []
}

function highlight(text, term){
  if (!term) return text
  const safe = term.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')
  const re = new RegExp(`(${safe})`,'ig')
  const parts = String(text).split(re)
  if (parts.length === 1) return text
  return parts.map((p,i)=> re.test(p) ? <mark key={i} className="bg-brand-500/25 text-brand-800 font-medium rounded px-0.5">{p}</mark> : p )
}

function ControlsBar({
  compact,
  search,
  setSearch,
  canNavigateSearch,
  filteredLength,
  isMobile,
  subtheme,
  searchNavIndex,
  goPrev,
  goNext,
  goFirst,
  setSearchInputRef,
}) {
  return (
    <>
      <div className="relative">
        <input
          ref={setSearchInputRef}
          value={search}
          onChange={e=>setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && canNavigateSearch) {
              e.preventDefault()
              goFirst()
            }
          }}
          placeholder="Buscar… (/ atalho)"
          aria-label="Buscar regras"
          className={`w-full rounded-lg border border-brand-200/70 bg-white px-3 ${compact ? 'py-2' : 'py-3 sm:py-2'} text-[16px] sm:text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 shadow-sm shadow-slate-200/70 min-h-11`}
        />
        {search && (
          <button
            type="button"
            onClick={()=>setSearch('')}
            aria-label="Limpar busca"
            className="absolute right-1 top-1/2 -translate-y-1/2 text-xs text-slate-500 hover:text-slate-700 p-2"
          >×</button>
        )}
      </div>

      {canNavigateSearch && (
        <div className={`flex items-center justify-between gap-2 rounded-lg border border-brand-200/60 bg-white/80 px-3 ${compact ? 'py-1.5' : 'py-2'} text-[12px] text-slate-700 shadow-sm shadow-slate-200/70`}>
          <div className="min-w-0 truncate">
            <span className="text-slate-600">Resultados:</span>{' '}
            <strong className="text-brand-800">{filteredLength}</strong>
            {isMobile && subtheme && (
              <span className="ml-2 text-[11px] text-slate-500">(busca em todos)</span>
            )}
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              type="button"
              onClick={goPrev}
              className="rounded-md border border-brand-200/70 bg-white px-2 py-1 text-[11px] text-slate-700 hover:bg-brand-50/40 transition-colors"
              aria-label="Resultado anterior"
            >Anterior</button>
            <span className="px-2 text-[11px] text-slate-600 tabular-nums">{Math.min(filteredLength, searchNavIndex + 1)}/{filteredLength}</span>
            <button
              type="button"
              onClick={goNext}
              className="rounded-md border border-brand-200/70 bg-white px-2 py-1 text-[11px] text-slate-700 hover:bg-brand-50/40 transition-colors"
              aria-label="Próximo resultado"
            >Próximo</button>
          </div>
        </div>
      )}
    </>
  )
}

export default function App(){
  const [rules, setRules] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState(null)
  const [isMobile, setIsMobile] = useState(false)
  const [openAttachmentId, setOpenAttachmentId] = useState(null)
  const itemRefs = useRef(new Map())
  const buttonRefs = useRef(new Map())
  const listScrollRef = useRef(null)
  const controlsInFlowRef = useRef(null)
  const fixedControlsRef = useRef(null)
  const [showFixedControls, setShowFixedControls] = useState(false)
  const [fixedControlsHeight, setFixedControlsHeight] = useState(0)
  const scrollTimersRef = useRef([])
  const scrollAnimRef = useRef(null)
  const scrollFollowRef = useRef({ stableFrames: 0, startTs: 0, lastTs: 0 })
  const [focusIndex, setFocusIndex] = useState(0)
  const [search, setSearch] = useState('')
  const [subtheme, setSubtheme] = useState('')
  const [searchNavIndex, setSearchNavIndex] = useState(0)
  const searchRef = useRef(null)
  const reportedTermsRef = useRef(new Set())
  const [controlsFocused, setControlsFocused] = useState(false)
  const [atTop, setAtTop] = useState(true)

  useEffect(() => {
    return () => {
      for (const t of scrollTimersRef.current) clearTimeout(t)
      scrollTimersRef.current = []
      if (scrollAnimRef.current) cancelAnimationFrame(scrollAnimRef.current)
      scrollAnimRef.current = null
    }
  }, [])

  // Fetch rules
  useEffect(()=>{
    setLoading(true)
    fetch('/api/rules/')
      .then(r=>r.json())
      .then(json=>{
        const rs = json.results || []
        setRules(rs)
        // Não auto-abrir nenhum item no carregamento.
        setLoading(false)
      })
      .catch((e)=>{
        console.error(e)
        setLoading(false)
      })
  }, [])

  // Detecta se o usuário está no topo da página.
  // No topo, não queremos a barra fixa sobrepondo o título.
  useEffect(() => {
    const onScroll = () => setAtTop((window.scrollY || 0) <= 4)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
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

  useEffect(() => {
    const el = controlsInFlowRef.current
    if (!el) return

    // Importante: durante digitação, não escondemos a barra fixa.
    // Isso evita unmount/remount do input e perda de foco a cada letra.
    const io = new IntersectionObserver(
      ([entry]) => {
        setShowFixedControls(prev => {
          if (!entry.isIntersecting) return true
          if (controlsFocused) return prev
          return false
        })
      },
      { root: null, threshold: 0 }
    )
    io.observe(el)
    return () => io.disconnect()
  }, [controlsFocused])

  useEffect(() => {
    if (controlsFocused) return
    if (!showFixedControls) return
    if (atTop) {
      setShowFixedControls(false)
      return
    }
    const el = controlsInFlowRef.current
    if (!el) return
    // Ao perder foco, se o controle “original” já está visível, esconda o fixo.
    const r = el.getBoundingClientRect()
    const inView = r.bottom > 0 && r.top < (window.innerHeight || 0)
    if (inView) setShowFixedControls(false)
  }, [controlsFocused, showFixedControls, atTop])

  useEffect(() => {
    if (!showFixedControls) {
      setFixedControlsHeight(0)
      return
    }

    const el = fixedControlsRef.current
    if (!el || typeof ResizeObserver === 'undefined') return

    const measure = () => {
      const h = Math.round(el.getBoundingClientRect().height)
      if (h) setFixedControlsHeight(h)
    }
    measure()

    const ro = new ResizeObserver(() => measure())
    ro.observe(el)
    return () => ro.disconnect()
  }, [showFixedControls])

  useEffect(() => {
    if (!window.visualViewport) return
    let raf = 0
    const vv = window.visualViewport
    const update = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const root = document.documentElement
        root.style.setProperty('--vv-offset-top', `${Math.max(0, vv.offsetTop)}px`)
        root.style.setProperty('--vv-offset-left', `${Math.max(0, vv.offsetLeft)}px`)
      })
    }
    update()
    vv.addEventListener('scroll', update)
    vv.addEventListener('resize', update)
    return () => {
      cancelAnimationFrame(raf)
      vv.removeEventListener('scroll', update)
      vv.removeEventListener('resize', update)
    }
  }, [])

  const stickyTopOffset = useMemo(() => {
    if (showFixedControls && fixedControlsHeight) return fixedControlsHeight + 16
    return isMobile ? 96 : 12
  }, [showFixedControls, fixedControlsHeight, isMobile])

  const globalCategory = useMemo(() => {
    const categories = new Set(
      rules
        .map(r => (r.category || '').trim())
        .filter(Boolean)
    )
    if (categories.size === 1) return Array.from(categories)[0]
    return null
  }, [rules])

  const prefersReducedMotion = useMemo(
    () => matchMedia('(prefers-reduced-motion: reduce)').matches,
    []
  )

  // Evita falso-positivo do eslint com <motion.div /> (JSX member expression)
  // e garante uma referência estável ao componente.
  const MotionDiv = motion.div
  const MotionUl = motion.ul
  const MotionLi = motion.li
  const MotionButton = motion.button
  const MotionP = motion.p
  const MotionSection = motion.section

  // Timing: mais “perceptível” para leigos (sem parecer bug), mas sem virar show.
  const listAnim = useMemo(
    () => ({ duration: prefersReducedMotion ? 0 : 0.34, ease: [0.2, 0, 0, 1] }),
    [prefersReducedMotion]
  )
  const panelAnim = useMemo(
    () => ({ duration: prefersReducedMotion ? 0 : 0.42, ease: [0.2, 0, 0, 1] }),
    [prefersReducedMotion]
  )

  const listItemVariants = useMemo(() => ({
    hidden: { opacity: 0, y: 18 },
    show: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -14 },
  }), [])

  const panelContentVariants = useMemo(() => ({
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: prefersReducedMotion
        ? { duration: 0 }
        : { staggerChildren: 0.08, delayChildren: 0.10 },
    },
    exit: {
      opacity: 0,
      transition: prefersReducedMotion
        ? { duration: 0 }
        : { staggerChildren: 0.06, staggerDirection: -1 },
    },
  }), [prefersReducedMotion])

  const panelChildVariants = useMemo(() => ({
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: prefersReducedMotion ? 0 : 0.32, ease: [0.2, 0, 0, 1] } },
    exit: { opacity: 0, y: -10, transition: { duration: prefersReducedMotion ? 0 : 0.20, ease: [0.2, 0, 0, 1] } },
  }), [prefersReducedMotion])

  const previewSnippetsVariants = useMemo(() => ({
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: prefersReducedMotion
        ? { duration: 0 }
        : { staggerChildren: 0.10, delayChildren: 0.06 },
    },
  }), [prefersReducedMotion])

  const previewSnippetItemVariants = useMemo(() => ({
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0, transition: { duration: prefersReducedMotion ? 0 : 0.30, ease: [0.2, 0, 0, 1] } },
  }), [prefersReducedMotion])

  // Mobile: não auto-expandir durante scroll.
  // Isso evita “pulos” de leitura quando a altura dos cards muda.

  const handleMouseEnter = (id) => {
    // Não expandir por hover no desktop: evita “paredão” ao passar o mouse.
    // Mantemos expansão por clique/teclado e por foco.
    void id
  }

  const getRuleTargetTop = useCallback((id) => {
    const el = itemRefs.current.get(id)
    if (!el) return null
    const scroller = listScrollRef.current
    const rect = el.getBoundingClientRect()
    if (!scroller) {
      return Math.max(0, Math.round(rect.top + window.scrollY - stickyTopOffset))
    }
    const scrollerRect = scroller.getBoundingClientRect()
    return Math.max(0, Math.round((rect.top - scrollerRect.top) + scroller.scrollTop - stickyTopOffset))
  }, [stickyTopOffset])

  const scrollToRuleStart = useCallback((id, { behavior } = {}) => {
    const requested = behavior || 'smooth'

    const scroller = listScrollRef.current
    const scrollToTop = (top, b) => {
      if (!scroller) {
        window.scrollTo({ top, behavior: b })
        return
      }
      scroller.scrollTo({ top, behavior: b })
    }
    const getCurrentTop = () => (scroller ? scroller.scrollTop : window.scrollY)

    const snap = () => {
      const targetTop = getRuleTargetTop(id)
      if (targetTop == null) return
      scrollToTop(targetTop, 'auto')
    }

    if (prefersReducedMotion || requested === 'auto') {
      if (scrollAnimRef.current) cancelAnimationFrame(scrollAnimRef.current)
      scrollAnimRef.current = null
      snap()
      return
    }

    // "Scroll follow" curto: acompanha o topo do card enquanto o layout muda
    // (ex.: card anterior recolhendo e empurrando o conteúdo para cima).
    if (scrollAnimRef.current) cancelAnimationFrame(scrollAnimRef.current)
    scrollAnimRef.current = null

    const state = scrollFollowRef.current
    state.stableFrames = 0
    state.startTs = performance.now()
    state.lastTs = state.startTs
    const maxMs = 700
    const tauMs = 170
    const stableNeeded = 8

    const step = (now) => {
      const targetTop = getRuleTargetTop(id)
      if (targetTop == null) {
        scrollAnimRef.current = null
        return
      }

      const currentTop = getCurrentTop()
      const err = targetTop - currentTop

      const dtRaw = Math.max(1, now - state.lastTs)
      // Evita “saltos” quando o main thread engasga: limita o dt usado no filtro.
      const dt = Math.min(32, dtRaw)
      state.lastTs = now

      if (Math.abs(err) < 1.5) state.stableFrames += 1
      else state.stableFrames = 0

      const elapsed = now - state.startTs
      if (state.stableFrames >= stableNeeded || elapsed > maxMs) {
        const finalErr = targetTop - getCurrentTop()
        // Finaliza sem “snap” agressivo quando ainda há distância.
        if (Math.abs(finalErr) > 6) {
          scrollToTop(Math.round(targetTop), 'smooth')
        } else {
          scrollToTop(Math.round(targetTop), 'auto')
        }
        scrollAnimRef.current = null
        return
      }

      // Filtro exponencial (suave e responsivo): aproxima sem “travadas”.
      const k = 1 - Math.exp(-dt / tauMs)
      let delta = err * k
      // Limita o deslocamento por frame para manter percepção “constante”.
      const maxDelta = 90
      if (delta > maxDelta) delta = maxDelta
      if (delta < -maxDelta) delta = -maxDelta
      scrollToTop(Math.round(currentTop + delta), 'auto')
      scrollAnimRef.current = requestAnimationFrame(step)
    }

    scrollAnimRef.current = requestAnimationFrame(step)
  }, [getRuleTargetTop, prefersReducedMotion])

  const scrollToFirstMatch = useCallback((id) => {
    const el = itemRefs.current.get(id)
    if (!el) return
    const mark = el.querySelector('mark')
    if (!mark) {
      // Fallback: pelo menos alinha o início do card.
      scrollToRuleStart(id, { behavior: 'smooth' })
      return
    }

    const scroller = listScrollRef.current
    if (!scroller) {
      // Centraliza o highlight na tela para poupar scroll manual.
      // (Útil principalmente no mobile com cards longos.)
      mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }

    // Centraliza dentro do container scrollável.
    const markRect = mark.getBoundingClientRect()
    const scrollerRect = scroller.getBoundingClientRect()
    const markTop = (markRect.top - scrollerRect.top) + scroller.scrollTop
    const markCenter = markTop + (markRect.height / 2)
    const targetTop = Math.max(0, Math.round(markCenter - (scroller.clientHeight / 2)))
    scroller.scrollTo({ top: targetTop, behavior: 'smooth' })
  }, [scrollToRuleStart])

  const openRule = useCallback((id, { scroll } = { scroll: false }) => {
    if (scroll) {
      // Inicia scroll imediatamente e expande com leve defasagem.
      // Isso reduz a competição por layout e evita a sensação de “engasgo”.
      for (const t of scrollTimersRef.current) clearTimeout(t)
      scrollTimersRef.current = []

      // Inicia o follow já no clique para lidar com layout mudando.
      scrollToRuleStart(id, { behavior: 'smooth' })

      const expandDelay = prefersReducedMotion ? 0 : 60
      const tExpand = setTimeout(() => setExpandedId(id), expandDelay)
      scrollTimersRef.current.push(tExpand)

      // Snap final após a animação de colapso/expansão para garantir alinhamento perfeito.
      const tFix = setTimeout(() => scrollToRuleStart(id, { behavior: 'auto' }), expandDelay + 560)
      scrollTimersRef.current.push(tFix)

      // Se há busca ativa, após a animação de abertura terminar,
      // centraliza o primeiro termo destacado.
      const term = search.trim()
      if (term) {
        const tCenter = setTimeout(
          () => scrollToFirstMatch(id),
          prefersReducedMotion ? 0 : expandDelay + 720
        )
        scrollTimersRef.current.push(tCenter)
      }
      return
    }
    setExpandedId(id)
  }, [scrollToRuleStart, prefersReducedMotion, search, scrollToFirstMatch])
  
  // (openRule usa prefersReducedMotion indiretamente via expandDelay)

  const handleFocus = (id, idx) => {
    setFocusIndex(idx)
    void id
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
      openRule(rule.id, { scroll: true })
    }
  }

  // Filtragem
  const filtered = useMemo(()=>{
    const t = search.trim().toLowerCase()
    // No mobile, quando há termo de busca, procuramos em TODOS os subtemas
    // (o usuário não precisa lembrar/alternar subtema para achar).
    const shouldApplySubtheme = !!subtheme && !(isMobile && t)
    const bySubtheme = shouldApplySubtheme ? rules.filter(r => String(r.id) === String(subtheme)) : rules
    if (!t) return bySubtheme
    return bySubtheme.filter(r => {
      if (r.title?.toLowerCase().includes(t)) return true
      if (r.category?.toLowerCase().includes(t)) return true
      if (r.cards?.some(c => c.bullets?.some(b => b.text?.toLowerCase().includes(t)))) return true
      if (r.body?.toLowerCase().includes(t)) return true
      return false
    })
  }, [rules, search, subtheme, isMobile])

  const canNavigateSearch = search.trim() && !loading && filtered.length > 0

  const goToSearchIndex = useCallback((nextIndex) => {
    if (!filtered.length) return
    const normalized = ((nextIndex % filtered.length) + filtered.length) % filtered.length
    setSearchNavIndex(normalized)
    const id = filtered[normalized].id
    openRule(id, { scroll: true })
    const t = setTimeout(() => scrollToFirstMatch(id), prefersReducedMotion ? 0 : 540)
    scrollTimersRef.current.push(t)
  }, [filtered, openRule, scrollToFirstMatch, prefersReducedMotion])

  // Ao mudar os resultados, mantém o índice dentro do range
  useEffect(() => {
    if (!filtered.length) {
      if (searchNavIndex !== 0) setSearchNavIndex(0)
      return
    }
    if (searchNavIndex >= filtered.length) setSearchNavIndex(0)
  }, [filtered, searchNavIndex])

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

  const empty = !loading && filtered.length === 0
  const few = !loading && !empty && filtered.length < 3 && search.trim()
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

  const skeletonCount = isMobile ? 4 : 6
  const controlsSpacerHeight = fixedControlsHeight || (isMobile ? 112 : 88)

  const setSearchInputRef = useCallback((el) => {
    if (el) searchRef.current = el
  }, [])

  const goSearchPrev = useCallback(() => goToSearchIndex(searchNavIndex - 1), [goToSearchIndex, searchNavIndex])
  const goSearchNext = useCallback(() => goToSearchIndex(searchNavIndex + 1), [goToSearchIndex, searchNavIndex])
  const goSearchFirst = useCallback(() => goToSearchIndex(0), [goToSearchIndex])

  return (
    <MotionConfig reducedMotion={prefersReducedMotion ? 'always' : 'never'}>
    <div className="mx-auto w-full max-w-4xl px-4 py-6 sm:py-8 font-sans">
      <AnimatePresence initial={false}>
        {showFixedControls && !atTop && (
          <div
            className="fixed left-0 right-0 z-50 pointer-events-none"
            style={{
              top: 'calc(env(safe-area-inset-top) + 12px)',
              transform: 'translate3d(var(--vv-offset-left, 0px), var(--vv-offset-top, 0px), 0)',
            }}
          >
          <motion.div
            initial={{ opacity: 0, y: -14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -14 }}
            transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.30, ease: [0.2, 0, 0, 1] }}
          >
            <div className="mx-auto w-full max-w-4xl px-4 pointer-events-auto">
              <div
                ref={fixedControlsRef}
                onFocusCapture={() => setControlsFocused(true)}
                onBlurCapture={(e) => {
                  if (e.currentTarget.contains(e.relatedTarget)) return
                  setControlsFocused(false)
                }}
                className="rounded-xl border border-brand-200/50 bg-white/70 shadow-sm shadow-slate-200/70 backdrop-blur-sm px-3 py-3"
              >
                <div className="flex flex-col gap-2">
                  <ControlsBar
                    compact
                    search={search}
                    setSearch={setSearch}
                    canNavigateSearch={canNavigateSearch}
                    filteredLength={filtered.length}
                    isMobile={isMobile}
                    subtheme={subtheme}
                    searchNavIndex={searchNavIndex}
                    goPrev={goSearchPrev}
                    goNext={goSearchNext}
                    goFirst={goSearchFirst}
                    setSearchInputRef={setSearchInputRef}
                  />
                </div>
              </div>
            </div>
          </motion.div>
          </div>
        )}
      </AnimatePresence>

      <header className="mb-5 sm:mb-6 flex flex-col gap-3 sm:gap-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-brand-700">Manual de Normas e Rotinas Médicas</h1>
            {globalCategory && (
              <div className="mt-2">
                <span className="inline-flex items-center rounded-md bg-brand-50/60 px-2 py-0.5 uppercase tracking-wide text-brand-800/80 border border-brand-200/50 text-[11px]">
                  {globalCategory}
                </span>
              </div>
            )}
            <p className="text-sm text-slate-800 mt-2">Consulte e, se não achar, envie sua dúvida para ampliar a base.</p>
            <p className="text-[11px] text-slate-600 mt-2">Atalhos: / busca · Esc limpa · ↑ ↓ navegam · Home/End · Enter/Espaço expandem.</p>
          </div>
          <div className="flex items-center gap-2">
            <a href={askHref} className="inline-flex items-center gap-2 rounded-lg border border-brand-200 bg-white hover:bg-brand-50 text-sm sm:text-xs font-semibold px-4 py-2.5 sm:py-2 text-brand-800 transition-colors min-h-11">
              <span>+ Perguntar</span>
            </a>
          </div>
        </div>
        <div
          ref={controlsInFlowRef}
          onFocusCapture={() => setControlsFocused(true)}
          onBlurCapture={(e) => {
            if (e.currentTarget.contains(e.relatedTarget)) return
            setControlsFocused(false)
          }}
          className="flex flex-col gap-2"
        >
          {showFixedControls && !atTop ? (
            <div aria-hidden="true" style={{ height: controlsSpacerHeight }} />
          ) : (
            <ControlsBar
              search={search}
              setSearch={setSearch}
              canNavigateSearch={canNavigateSearch}
              filteredLength={filtered.length}
              isMobile={isMobile}
              subtheme={subtheme}
              searchNavIndex={searchNavIndex}
              goPrev={goSearchPrev}
              goNext={goSearchNext}
              goFirst={goSearchFirst}
              setSearchInputRef={setSearchInputRef}
            />
          )}
        </div>

        <div className="flex flex-col gap-2">
          {!loading && empty && search.trim() && (
            <div role="status" className="rounded-lg border border-brand-200/70 bg-brand-50/30 px-3 py-3 text-[13px] text-slate-800 shadow-sm">
              Nenhuma regra encontrada para <strong className="text-brand-700">{search}</strong>.
              <a href={askHref} className="ml-1 text-brand-600 hover:text-brand-700 underline decoration-dotted">Enviar essa dúvida?</a>
            </div>
          )}
          {!loading && few && (
            <div className="text-[11px] text-slate-500">
              Poucos resultados. Se ainda está com dúvida,
              <a href={askHref} className="ml-1 text-brand-600 hover:text-brand-700 underline">pergunte</a>.
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="text-[11px] uppercase tracking-wide text-brand-700/80" htmlFor="subtheme">Subtema</label>
          <select
            id="subtheme"
            value={subtheme}
            onChange={(e)=>setSubtheme(e.target.value)}
            className="w-full sm:w-auto rounded-lg border border-brand-200/70 bg-white px-3 py-3 sm:py-2 text-[16px] sm:text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 shadow-sm min-h-11"
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

      <MotionUl
        layout
        className={`flex flex-col gap-3 no-scroll-anchor transition-opacity duration-200 ease-out pb-24 ${loading ? 'opacity-80' : 'opacity-100'}`}
        aria-label="Lista de regras"
        role="list"
        aria-busy={loading ? 'true' : 'false'}
      >
        {loading && (
          Array.from({ length: skeletonCount }).map((_, i) => (
            <li
              key={`sk-${i}`}
              className="rounded-xl border border-brand-200/50 bg-white/60 px-5 py-4 shadow-sm shadow-slate-200/60"
            >
              <div className="animate-pulse">
                <div className="flex items-start gap-3">
                  <div className="mt-1.5 h-2 w-2 rounded-full bg-brand-300/50 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="h-4 w-2/3 rounded bg-slate-200/70" />
                    <div className="mt-2 flex items-center gap-2">
                      <div className="h-4 w-20 rounded bg-brand-100/70" />
                      <div className="h-4 w-32 rounded bg-slate-200/60" />
                    </div>
                    <div className="mt-3 h-3 w-5/6 rounded bg-slate-200/60" />
                  </div>
                </div>
              </div>
            </li>
          ))
        )}

        {!loading && empty && search.trim() && (
          <li className="text-sm text-slate-700 px-2 py-10 text-center border border-brand-200/70 rounded-xl bg-brand-50/30 shadow-sm">Nenhuma regra corresponde à busca.</li>
        )}
        {!loading && (
          <AnimatePresence initial={false} mode="popLayout">
            {filtered.map((rule, idx) => {
              const expanded = expandedId === rule.id
              const preview = getRulePreview(rule) || '(Sem conteúdo)'
              const excerpts = search.trim() ? getRuleSearchExcerpts(rule, search.trim()) : []
              const focused = idx === focusIndex
              return (
                <MotionLi
                  layout="position"
                  key={rule.id}
                  variants={listItemVariants}
                  initial="hidden"
                  animate="show"
                  exit="exit"
                  transition={listAnim}
                  ref={el => itemRefs.current.set(rule.id, el)}
                  style={{ scrollMarginTop: `${stickyTopOffset}px` }}
                  className={`group relative rounded-xl border bg-white/70 shadow-sm shadow-slate-200/60 transition-colors duration-[260ms] ease-out focus-within:ring-1 focus-within:ring-brand-400/40
                    ${expanded
                      ? 'border-brand-300 bg-brand-50/45 shadow-md shadow-slate-200/70'
                      : 'border-slate-200 hover:border-brand-200 hover:bg-white/65 hover:shadow-md hover:shadow-slate-200/70'}
                    ${expanded
                      ? 'before:absolute before:inset-y-0 before:left-0 before:w-1 before:rounded-l-xl before:bg-accent-500/55'
                      : ''}`}
                  role="listitem"
                >
                  <MotionButton
                    ref={el => buttonRefs.current.set(rule.id, el)}
                    type="button"
                    whileHover={prefersReducedMotion ? undefined : { scale: 1.02 }}
                    whileTap={prefersReducedMotion ? undefined : { scale: 0.97 }}
                    transition={prefersReducedMotion ? undefined : { type: 'spring', stiffness: 560, damping: 34, mass: 0.75 }}
                    style={{ willChange: 'transform' }}
                    className={`w-full text-left px-5 py-4 outline-none rounded-xl transition-colors duration-[260ms] ease-out
                      ${focused ? 'ring-2 ring-brand-400/60 ring-offset-2 ring-offset-slate-50' : ''}`}
                    aria-expanded={expanded}
                    aria-controls={`rule-panel-${rule.id}`}
                    onMouseEnter={()=>handleMouseEnter(rule.id)}
                    onFocus={()=>handleFocus(rule.id, idx)}
                    onClick={() => {
                      if (expandedId !== rule.id) {
                        openRule(rule.id, { scroll: true })
                      } else {
                        // Mesmo já aberto, garante que o usuário vá para o início.
                        scrollToRuleStart(rule.id)
                      }
                    }}
                    onKeyDown={(e)=>handleKeyDown(e, idx, rule)}
                  >
                <div className="flex items-start gap-3">
                  <div className={`mt-1.5 h-2 w-2 rounded-full flex-shrink-0 transition-colors duration-[220ms] ease-out
                    ${expanded ? 'bg-brand-600' : 'bg-slate-300 group-hover:bg-brand-400'}`}/>
                  <div className="flex-1 min-w-0">
                    <h2 className={`text-sm font-semibold tracking-wide transition-colors duration-150 line-clamp-2 sm:line-clamp-1
                      ${expanded ? 'text-brand-800' : 'text-slate-800 group-hover:text-brand-800'}`}>{highlight(rule.title, search)}</h2>
                    <div className="flex flex-wrap gap-x-2 gap-y-1 mt-1 items-center text-[11px]">
                      {rule.category && (!globalCategory || rule.category !== globalCategory) && (
                        <span className="inline-flex items-center rounded-md bg-brand-50/60 px-2 py-0.5 uppercase tracking-wide text-brand-800/80 border border-brand-200/50">
                          {highlight(rule.category, search)}
                        </span>
                      )}
                      {search && !expanded && (
                        <span className="text-slate-300">•</span>
                      )}
                      {search && !expanded && (
                        excerpts.length ? (
                          <MotionDiv
                            variants={previewSnippetsVariants}
                            initial="hidden"
                            animate="show"
                            className="mt-1 space-y-1"
                          >
                            {excerpts.map((txt, i) => (
                              <MotionDiv
                                key={`${rule.id}-ex-${i}`}
                                variants={previewSnippetItemVariants}
                                className="block text-[11px] text-slate-600 leading-snug line-clamp-2"
                              >
                                {highlight(txt, search)}
                              </MotionDiv>
                            ))}
                          </MotionDiv>
                        ) : (
                          <span className="block text-[11px] text-slate-600 leading-snug line-clamp-2">
                            {highlight(preview.slice(0, 160) + (preview.length > 160 ? '…' : ''), search)}
                          </span>
                        )
                      )}
                    </div>
                  </div>
                </div>
                  </MotionButton>

                  <div
                    id={`rule-panel-${rule.id}`}
                    role="region"
                    aria-label={`Conteúdo da regra ${rule.title}`}
                  >
                    <AnimatePresence initial={false} mode="wait">
                      {expanded && (
                        <MotionDiv
                          key={`panel-${rule.id}`}
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={panelAnim}
                          style={{ overflow: 'hidden' }}
                        >
                          <MotionDiv
                            variants={panelContentVariants}
                            initial="hidden"
                            animate="show"
                            exit="exit"
                            className="pt-3 pl-[22px] pr-1"
                          >
                            <div className="sticky top-2 z-10 flex justify-end pr-3">
                              <button
                                type="button"
                                onClick={() => setExpandedId(null)}
                                className="rounded-md border border-brand-200/70 bg-white/90 px-2 py-1 text-[11px] font-semibold text-slate-700 hover:bg-brand-50/40 transition-colors shadow-sm"
                                aria-label={`Fechar ${rule.title}`}
                              >
                                Fechar
                              </button>
                            </div>

                            {rule.body?.trim() && (
                              <div className="text-[14px] sm:text-[15px] leading-relaxed text-slate-700 text-justified">
                                {String(rule.body).split(/\n{2,}/).map((p, i) => (
                                  <MotionP key={i} variants={panelChildVariants} className={i ? 'mt-3' : ''}>{highlight(p, search)}</MotionP>
                                ))}
                              </div>
                            )}

                            {rule.cards?.length > 0 && (
                              <MotionDiv variants={panelChildVariants} className="mt-3 grid grid-cols-1 gap-3">
                                {rule.cards.map((c) => (
                                  <MotionSection
                                    key={c.id}
                                    variants={panelChildVariants}
                                    className="rounded-lg border border-brand-200/60 bg-white/92 px-4 py-3 shadow-sm shadow-slate-200/60"
                                    aria-label={`Card ${c.title}`}
                                  >
                                    <h3 className="text-[12px] font-semibold text-slate-800">{highlight(c.title, search)}</h3>
                                    <ul className="mt-2 flex flex-col gap-1">
                                      {(c.bullets || []).map((b) => (
                                        <li
                                          key={b.id}
                                          className="text-[13px] sm:text-[14px] text-slate-700 pl-3 relative before:absolute before:left-0 before:top-2 before:h-1 before:w-1 before:rounded-full before:bg-brand-500/70 text-justified"
                                        >
                                          {highlight(b.text, search)}
                                        </li>
                                      ))}
                                    </ul>
                                  </MotionSection>
                                ))}
                              </MotionDiv>
                            )}
                          </MotionDiv>
                        </MotionDiv>
                      )}
                    </AnimatePresence>
                  </div>
                </MotionLi>
              )
            })}
          </AnimatePresence>
        )}
      </MotionUl>

      {ATTACHMENTS.length > 0 && (
        <section className="mt-4 mb-28 rounded-xl border border-brand-200/50 bg-white/70 shadow-sm shadow-slate-200/60 backdrop-blur-sm p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-brand-700">Anexos</div>
            <div className="text-[11px] text-slate-600">{ATTACHMENTS.length} imagem(ns)</div>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {ATTACHMENTS.map((a) => {
              const open = openAttachmentId === a.id
              return (
                <div key={a.id} className="rounded-lg border border-brand-200/50 bg-white/80 overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setOpenAttachmentId(open ? null : a.id)}
                    className="w-full flex items-center justify-between gap-3 px-3 py-2 text-left hover:bg-brand-50/30 transition-colors"
                    aria-expanded={open}
                  >
                    <span className="text-[13px] font-semibold text-slate-800">{a.title}</span>
                    <span className="text-xs text-slate-500">{open ? 'Fechar' : 'Ver'}</span>
                  </button>

                  {open && (
                    <div className="px-3 pb-3">
                      <div className="mt-2 rounded-lg border border-brand-200/40 bg-white">
                        <img
                          src={a.href}
                          alt={a.title}
                          loading="lazy"
                          className="w-full h-auto rounded-lg"
                        />
                      </div>
                      <div className="mt-2 flex items-center justify-end">
                        <a
                          href={a.href}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[12px] text-brand-700 hover:text-brand-800 underline decoration-dotted"
                        >
                          Abrir em nova aba
                        </a>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* Botão flutuante permanente */}
      <a
        href={askHref}
        aria-label="Enviar nova pergunta"
        className="fixed bottom-5 right-5 inline-flex items-center gap-2 rounded-full bg-brand-600 hover:bg-brand-700 text-xs font-semibold px-5 py-3 shadow-lg shadow-brand-500/20 transition-colors group text-white"
      >
        <span className="h-2 w-2 rounded-full bg-white/70 group-hover:bg-white transition-colors"></span>
        <span>Perguntar</span>
      </a>
    </div>
    </MotionConfig>
  )
}
