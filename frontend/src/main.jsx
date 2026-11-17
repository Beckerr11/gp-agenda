import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { CalendarDays, UsersRound, Wrench, Plus, LogOut, ArrowRight, Clock3, Check, ChevronDown, ReceiptText, Menu, X } from 'lucide-react';
import CountUp from './components/CountUp';
import '@fontsource/dm-sans/latin-400.css';
import '@fontsource/dm-sans/latin-500.css';
import '@fontsource/dm-sans/latin-600.css';
import '@fontsource/dm-sans/latin-700.css';
import '@fontsource/oswald/latin-400.css';
import '@fontsource/oswald/latin-500.css';
import '@fontsource/oswald/latin-600.css';
import './app.css';
import './premium.css';

const labels = { agendado: 'Agendado', confirmado: 'Confirmado', em_execucao: 'Em execução', concluido: 'Concluído', cancelado: 'Cancelado' };
const money = cents => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(cents / 100);
const dateText = iso => new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso));

function App() {
  const reducedMotion = useReducedMotion();
  const [session, setSession] = useState(null);
  const [data, setData] = useState({ customers: [], services: [], appointments: [] });
  const [view, setView] = useState('overview');
  const [toast, setToast] = useState(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [busy, setBusy] = useState(false);

  const notice = useCallback((message, error = false) => {
    setToast({ message, error, id: Date.now() });
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4200);
    return () => clearTimeout(timer);
  }, [toast]);

  const load = useCallback(async () => {
    const response = await fetch('/api/data', { credentials: 'same-origin' });
    if (response.status === 401) { setSession(old => ({ ...old, authenticated: false })); return; }
    if (!response.ok) throw new Error('Não foi possível carregar os dados.');
    setData(await response.json());
  }, []);
  useEffect(() => {
    fetch('/api/session', { credentials: 'same-origin' })
      .then(r => r.json())
      .then(s => { setSession(s); if (s.authenticated) load().catch(e => notice(e.message, true)); })
      .catch(() => notice('Não foi possível conectar ao servidor.', true));
  }, [load, notice]);

  async function api(path, body) {
    setBusy(true);
    try {
      const response = await fetch(path, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
        body: JSON.stringify(body)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Não foi possível salvar.');
      return result;
    } finally { setBusy(false); }
  }
  async function save(path, body, success, next) {
    try {
      await api(path, body);
      await load();
      notice(success);
      if (next) setView(next);
      return true;
    } catch (e) { notice(e.message, true); return false; }
  }
  async function logout() {
    try {
      await api('/api/logout', {});
      setSession({ authenticated: false, csrf_token: '' });
      setData({ customers: [], services: [], appointments: [] });
      setView('overview');
    } catch (e) { notice(e.message, true); }
  }
  function navigate(next) { setView(next); setMobileNav(false); }

  if (!session) return <div className="boot"><div className="boot-mark">GP</div><span>Preparando a agenda</span></div>;
  if (!session.authenticated) return <Login session={session} setSession={setSession} load={load} notice={notice} busy={busy} setBusy={setBusy} toast={toast} />;

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'is-open' : ''}`}>
        <div className="brand-lockup"><div className="brand-icon">GP</div><div><b>GP Agenda</b><span>Estética Automotiva</span></div></div>
        <div className="workspace-label">Oficina do Ronaldo</div>
        <nav aria-label="Navegação principal">
          <NavButton icon={CalendarDays} label="Visão geral" active={view === 'overview'} onClick={() => navigate('overview')} />
          <NavButton icon={CalendarDays} label="Agenda" active={view === 'agenda'} onClick={() => navigate('agenda')} />
          <NavButton icon={UsersRound} label="Clientes" active={view === 'customers'} onClick={() => navigate('customers')} />
          <NavButton icon={Wrench} label="Serviços" active={view === 'services'} onClick={() => navigate('services')} />
        </nav>
        <div className="sidebar-bottom"><div className="sidebar-rule"></div><p>Controle da garagem,<br/>sem perder nenhum detalhe.</p><button onClick={logout} className="logout"><LogOut size={18} /> Sair da conta</button></div>
      </aside>
      {mobileNav && <button aria-label="Fechar menu" className="nav-scrim" onClick={() => setMobileNav(false)} />}
      <div className="main-shell">
        <header className="mobile-head"><button aria-label="Abrir menu" onClick={() => setMobileNav(true)}><Menu size={23}/></button><strong>GP Agenda</strong><span className="mobile-mark">GP</span></header>
        <main className="content"><AnimatePresence mode="wait"><motion.div key={view} initial={reducedMotion ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={reducedMotion ? { opacity: 1 } : { opacity: 0, y: -8 }} transition={{ duration: reducedMotion ? 0 : 0.25, ease: [0.22, 1, 0.36, 1] }}>
          {view === 'overview' && <Overview data={data} navigate={navigate} save={save} busy={busy} />}
          {view === 'agenda' && <Agenda data={data} save={save} navigate={navigate} busy={busy} />}
          {view === 'customers' && <Customers data={data} save={save} busy={busy} />}
          {view === 'services' && <Services data={data} save={save} busy={busy} />}
          {view === 'new' && <NewAppointment data={data} save={save} navigate={navigate} busy={busy} />}
        </motion.div></AnimatePresence></main>
      </div>
      <Toast toast={toast}/>
    </div>
  );
}

function NavButton({ icon: Icon, label, active, onClick }) {
  return <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick} aria-current={active ? 'page' : undefined}><Icon size={19} strokeWidth={1.8}/><span>{label}</span>{active && <motion.i layoutId="active-nav" transition={{ type: 'spring', stiffness: 450, damping: 34 }}/>}</button>;
}
function Toast({ toast }) {
  return <div role="status" aria-live="polite" className={`t-toast toast ${toast ? 'is-open' : ''} ${toast?.error ? 'toast-error' : ''}`}>
    {toast && <><span className="toast-symbol">{toast.error ? '!' : <Check size={16}/>}</span>{toast.message}</>}
  </div>;
}
function Login({ session, setSession, load, notice, busy, setBusy, toast }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  async function submit(e) {
    e.preventDefault(); setBusy(true);
    try {
      const r = await fetch('/api/login', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session.csrf_token },
        body: JSON.stringify({ username, password }) });
      const result = await r.json();
      if (!r.ok) throw new Error(result.error || 'Não foi possível entrar.');
      setSession(result); await load();
    } catch (error) { notice(error.message, true); } finally { setBusy(false); }
  }
  return <div className="login-layout">
    <div className="login-brand"><div className="brand-icon">GP</div><b>GP Agenda</b></div>
    <section className="login-story login-story--official">
      <img className="login-official-logo" src={import.meta.env.BASE_URL + 'images/gp-estetica-logo.jpg'} alt="Logo oficial da GP Estética Automotiva" width="900" height="1600" fetchPriority="high"/>
    </section>
    <section className="login-form-area"><div className="login-card"><span className="card-index">ACESSO DO RESPONSÁVEL</span><h2>Bem-vindo de volta.</h2><p>Entre para acompanhar a operação da GP.</p><form onSubmit={submit}><label>Usuário<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required/></label><label>Senha<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required/></label><button className="action" disabled={busy}>Entrar no painel <ArrowRight size={18}/></button></form><small>Acesso restrito à equipe da estética.</small></div></section><Toast toast={toast}/></div>;
}
function PageHeader({ eyebrow, title, description, action }) {
  return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}
function Overview({ data, navigate, save, busy }) {
  const reducedMotion = useReducedMotion();
  const counts = useMemo(() => data.appointments.reduce((a, item) => (a[item.status] = (a[item.status] || 0) + 1, a), {}), [data.appointments]);
  const active = data.appointments.filter(a => !['cancelado','concluido'].includes(a.status) && new Date(a.starts_at) >= new Date()).sort((a,b) => a.starts_at.localeCompare(b.starts_at));
  const next = active[0];
  return <>
    <motion.section className="photo-hero" aria-label="Visão conceitual da estética automotiva" initial={reducedMotion ? false : { opacity: 0, scale: .985 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: reducedMotion ? 0 : .65, ease: [0.22, 1, 0.36, 1] }}>
      <div className="photo-hero-top"><span>GP Estética Automotiva</span><span>Painel da operação</span></div>
      <div className="photo-hero-body"><h1>O cuidado começa<br/>na organização.</h1><p>Agenda, orçamentos e serviços no ritmo da sua garagem.</p><button className="photo-action" onClick={() => navigate('new')}>Criar agendamento <ArrowRight size={18}/></button></div>
      <div className="photo-hero-bottom"><span>GP / AGENDA</span><span>VISÃO DO DIA</span></div>
    </motion.section>
    <div className="operational-heading"><div><span className="section-numeral">01 / OPERAÇÃO</span><h2>O que acontece agora</h2></div><span>Uma visão direta do próximo carro e da fila.</span></div>
    <section className="hero-grid">
      <div className="next-card">
        <div className="card-top"><span>Próximo atendimento</span><CalendarDays size={20}/></div>
        {next ? <><div className="next-date">{dateText(next.starts_at)}</div><h2>{next.customer}</h2><p>{next.vehicle || 'Veículo não informado'} <span className="dot-sep"/> {next.service}</p><button className="inline-link" onClick={() => navigate('agenda')}>Ver na agenda <ArrowRight size={16}/></button></> :
          <><div className="next-empty">Agenda livre.</div><p>Crie o primeiro horário para organizar o fluxo da garagem.</p><button className="inline-link" onClick={() => navigate('new')}>Reservar horário <ArrowRight size={16}/></button></>}
        <div className="card-line" aria-hidden="true"></div>
      </div>
      <div className="metric-cluster">
        <Metric label="Aguardando" value={(counts.agendado || 0) + (counts.confirmado || 0)} note="agendados e confirmados"/>
        <Metric label="Em execução" value={counts.em_execucao || 0} note="em andamento"/>
        <Metric label="Concluídos" value={counts.concluido || 0} note="serviços finalizados"/>
      </div>
    </section>
    <section className="section-block">
      <div className="section-title"><div><h2>Fila de serviços</h2><p>Acompanhe o que está reservado e o que já foi entregue.</p></div><button className="quiet-link" onClick={() => navigate('agenda')}>Ver agenda completa <ArrowRight size={16}/></button></div>
      <AppointmentsTable items={data.appointments.slice(0, 6)} save={save} busy={busy} compact/>
    </section>
    <section className="quick-grid"><Quick icon={UsersRound} title="Clientes" value={data.customers.length} detail="cadastros organizados" onClick={() => navigate('customers')}/><Quick icon={Wrench} title="Serviços" value={data.services.length} detail="opções no catálogo" onClick={() => navigate('services')}/></section>
  </>;
}
function Metric({ label, value, note }) { return <div className="metric"><span>{label}</span><div className="metric-value"><CountUp to={value} duration={0.7} trigger="load"/></div><small>{note}</small></div>; }
function Quick({ icon: Icon, title, value, detail, onClick }) { const phrase = value === 1 ? detail.replace('cadastros organizados','cadastro organizado').replace('opções no catálogo','opção no catálogo') : detail; return <button className="quick" onClick={onClick}><div className="quick-icon"><Icon size={22}/></div><div><strong>{title}</strong><p><b>{value}</b> {phrase}</p></div><ArrowRight size={18}/></button>; }
function Status({ value }) { return <span className={`status status-${value}`}><i/>{labels[value]}</span>; }
function AppointmentsTable({ items, save, busy, compact = false }) {
  if (!items.length) return <div className="empty-state"><CalendarDays size={31} strokeWidth={1.3}/><h3>Nenhum horário por aqui</h3><p>Os agendamentos aparecem nesta lista assim que forem criados.</p></div>;
  return <div className="table-scroller"><table><thead><tr><th>Horário</th><th>Cliente e veículo</th><th>Serviço</th><th>Orçamento</th><th>Situação</th><th>Alterar</th><th>Documento</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><strong>{dateText(item.starts_at)}</strong><small>até {new Intl.DateTimeFormat('pt-BR',{hour:'2-digit',minute:'2-digit'}).format(new Date(item.ends_at))}</small></td><td><strong>{item.customer}</strong><small>{item.vehicle || 'Veículo não informado'}</small></td><td>{item.service}</td><td>{money(item.quoted_cents)}</td><td><Status value={item.status}/></td><td><StatusSelect item={item} save={save} busy={busy}/></td><td><a className="quote-link" href={`/appointments/${item.id}/quote`} target="_blank" rel="noopener noreferrer" aria-label={`Abrir orçamento de ${item.customer}`}><ReceiptText size={16}/> Abrir</a></td></tr>)}</tbody></table></div>;
}
function StatusSelect({ item, save, busy }) {
  const [status, setStatus] = useState(item.status);
  useEffect(() => setStatus(item.status), [item.status]);
  return <div className="status-edit"><label className="sr-only" htmlFor={`status-${item.id}`}>Status de {item.customer}</label><select id={`status-${item.id}`} value={status} onChange={e => setStatus(e.target.value)}>{Object.entries(labels).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select><button aria-label={`Salvar status de ${item.customer}`} disabled={busy || status === item.status} onClick={() => save(`/api/appointments/${item.id}/status`, { status }, 'Status atualizado.')}><Check size={17}/></button></div>;
}
function Agenda({ data, save, navigate, busy }) {
  const [filter, setFilter] = useState('todos');
  const items = data.appointments.filter(a => filter === 'todos' || a.status === filter);
  return <><PageHeader eyebrow="Planejamento" title="Agenda de serviços" description="Cada carro, horário e orçamento em uma linha clara." action={<button className="action header-action" onClick={() => navigate('new')}><Plus size={19}/> Novo agendamento</button>}/><div className="filter-bar"><span>{items.length} {items.length === 1 ? 'registro' : 'registros'}</span><label>Filtrar por situação <select value={filter} onChange={e => setFilter(e.target.value)}><option value="todos">Todas</option>{Object.entries(labels).map(([k,v]) => <option key={k} value={k}>{v}</option>)}</select></label></div><div className="data-panel"><AppointmentsTable items={items} save={save} busy={busy}/></div></>;
}
function Customers({ data, save, busy }) {
  const [form, setForm] = useState({ name: '', phone: '', vehicle: '' });
  async function submit(e) { e.preventDefault(); if (await save('/api/customers', form, 'Cliente cadastrado.')) setForm({ name: '', phone: '', vehicle: '' }); }
  return <><PageHeader eyebrow="Relacionamento" title="Clientes" description="Dados necessários para retornar a cada atendimento."/><div className="split-layout"><section className="form-panel"><div className="form-panel-head"><UsersRound size={22}/><div><h2>Novo cliente</h2><p>Comece pelo nome e veículo.</p></div></div><form onSubmit={submit}><Field label="Nome" required value={form.name} onChange={v => setForm({...form,name:v})}/><Field label="Telefone" type="tel" value={form.phone} onChange={v => setForm({...form,phone:v})}/><Field label="Veículo" placeholder="Modelo e placa, se necessário" value={form.vehicle} onChange={v => setForm({...form,vehicle:v})}/><button className="action" disabled={busy}>Salvar cliente <ArrowRight size={18}/></button></form></section><section className="list-panel"><div className="list-head"><h2>Clientes cadastrados</h2><span>{data.customers.length}</span></div>{data.customers.length ? data.customers.map(c => <div className="customer-row" key={c.id}><div className="avatar">{c.name.slice(0,1).toUpperCase()}</div><div><strong>{c.name}</strong><small>{c.vehicle || 'Veículo não informado'}</small></div><span>{c.phone}</span></div>) : <EmptyList icon={UsersRound} title="Sua lista começa aqui" text="Cadastre um cliente para vincular serviços e horários."/>}</section></div></>;
}
function Services({ data, save, busy }) {
  const [form, setForm] = useState({ name: '', duration_minutes: 60, base_price: '' });
  async function submit(e) { e.preventDefault(); if (await save('/api/services', form, 'Serviço cadastrado.')) setForm({ name: '', duration_minutes: 60, base_price: '' }); }
  return <><PageHeader eyebrow="Catálogo" title="Serviços" description="Duração e preço base deixam o atendimento mais previsível."/><div className="split-layout"><section className="form-panel"><div className="form-panel-head"><Wrench size={22}/><div><h2>Novo serviço</h2><p>Defina uma opção da estética.</p></div></div><form onSubmit={submit}><Field label="Nome do serviço" required placeholder="Ex.: lavagem detalhada" value={form.name} onChange={v => setForm({...form,name:v})}/><Field label="Duração em minutos" type="number" min="15" max="1440" step="15" required value={form.duration_minutes} onChange={v => setForm({...form,duration_minutes:v})}/><Field label="Preço base em reais" required placeholder="150,00" value={form.base_price} onChange={v => setForm({...form,base_price:v})}/><button className="action" disabled={busy}>Salvar serviço <ArrowRight size={18}/></button></form></section><section className="list-panel"><div className="list-head"><h2>Catálogo atual</h2><span>{data.services.length}</span></div>{data.services.length ? data.services.map(s => <div className="service-row" key={s.id}><div className="service-icon"><Wrench size={19}/></div><div><strong>{s.name}</strong><small><Clock3 size={13}/> {s.duration_minutes} min</small></div><b>{money(s.base_price_cents)}</b></div>) : <EmptyList icon={Wrench} title="Catálogo vazio" text="Cadastre o primeiro serviço para montar a agenda."/>}</section></div></>;
}
function NewAppointment({ data, save, navigate, busy }) {
  const [form, setForm] = useState({ customer_id: '', service_id: '', starts_at: '', quoted_price: '', notes: '' });
  const selected = data.services.find(s => String(s.id) === String(form.service_id));
  useEffect(() => { if (selected && !form.quoted_price) setForm(old => ({...old, quoted_price: (selected.base_price_cents / 100).toFixed(2).replace('.',',')})); }, [selected]);
  async function submit(e) { e.preventDefault(); if (await save('/api/appointments', form, 'Agendamento criado.', 'agenda')) setForm({ customer_id: '', service_id: '', starts_at: '', quoted_price: '', notes: '' }); }
  return <><PageHeader eyebrow="Nova ordem de serviço" title="Reservar horário" description="Defina o cliente, o trabalho e o valor combinado."/><div className="appointment-layout"><section className="form-panel"><div className="form-panel-head"><CalendarDays size={22}/><div><h2>Dados do atendimento</h2><p>O intervalo é reservado conforme a duração do serviço.</p></div></div>{(!data.customers.length || !data.services.length) && <div className="form-hint">Cadastre {data.customers.length ? '' : 'um cliente'}{!data.customers.length && !data.services.length ? ' e ' : ''}{data.services.length ? '' : 'um serviço'} antes de agendar.</div>}<form onSubmit={submit}><label className="field">Cliente<select required value={form.customer_id} onChange={e => setForm({...form,customer_id:e.target.value})}><option value="">Selecione um cliente</option>{data.customers.map(c => <option key={c.id} value={c.id}>{c.name} · {c.vehicle}</option>)}</select></label><label className="field">Serviço<select required value={form.service_id} onChange={e => setForm({...form,service_id:e.target.value,quoted_price:(e.target.value && data.services.find(s=>String(s.id)===e.target.value)?.base_price_cents / 100).toFixed(2).replace('.',',') || ''})}><option value="">Selecione um serviço</option>{data.services.map(s => <option key={s.id} value={s.id}>{s.name} · {s.duration_minutes} min</option>)}</select></label><div className="form-pair"><Field label="Data e hora" type="datetime-local" required value={form.starts_at} onChange={v => setForm({...form,starts_at:v})}/><Field label="Orçamento em reais" required placeholder="150,00" value={form.quoted_price} onChange={v => setForm({...form,quoted_price:v})}/></div><label className="field">Observações<textarea rows="3" maxLength="500" value={form.notes} onChange={e => setForm({...form,notes:e.target.value})} placeholder="Detalhes do atendimento"></textarea></label><div className="form-actions"><button type="button" className="ghost-button" onClick={() => navigate('agenda')}>Cancelar</button><button className="action" disabled={busy || !data.customers.length || !data.services.length}>Salvar agendamento <ArrowRight size={18}/></button></div></form></section><aside className="summary-panel"><div className="summary-top"><ReceiptText size={24}/><span>Resumo do serviço</span></div><h3>{selected?.name || 'Selecione um serviço'}</h3><div className="summary-line"><span>Duração prevista</span><strong>{selected ? `${selected.duration_minutes} min` : '—'}</strong></div><div className="summary-line"><span>Preço base</span><strong>{selected ? money(selected.base_price_cents) : '—'}</strong></div><div className="summary-note">O valor final do orçamento pode ser ajustado antes de salvar.</div></aside></div></>;
}
function Field({ label, onChange, ...props }) { return <label className="field">{label}<input onChange={e => onChange(e.target.value)} {...props}/></label>; }
function EmptyList({ icon: Icon, title, text }) { return <div className="empty-list"><Icon size={30} strokeWidth={1.3}/><h3>{title}</h3><p>{text}</p></div>; }

createRoot(document.getElementById('root')).render(<App />);
