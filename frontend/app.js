const $ = s => document.querySelector(s),
  esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])),
  money = n => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n);

let DESTINATIONS = [];
const currentDest = () => $('#destination').value;

function fillPlaces() {
  const d = DESTINATIONS.find(x => x.name === currentDest());
  $('#place').innerHTML = (d ? d.places : []).map(p => `<option>${esc(p)}</option>`).join('');
  const gd = $('#guide-dest'); if (gd) gd.textContent = `Your ${currentDest()} guide`;
  const ml = $('#maps-link');
  if (ml) { ml.href = 'https://www.google.com/maps/search/' + encodeURIComponent(currentDest() + ', India'); ml.textContent = `Open ${currentDest()} in Maps ↗`; }
}

async function loadDestinations() {
  try {
    const r = await fetch('/api/destinations');
    const d = await r.json();
    DESTINATIONS = d.destinations || [];
    const sel = $('#destination');
    sel.innerHTML = DESTINATIONS.map(x => `<option>${esc(x.name)}</option>`).join('');
    if (DESTINATIONS.length) sel.value = DESTINATIONS.some(x => x.name === 'Jaipur') ? 'Jaipur' : DESTINATIONS[0].name;
    const pill = $('#dest-pill'); if (pill) pill.textContent = `✦ ${DESTINATIONS.length} destinations ready to explore`;
    fillPlaces();
  } catch (e) { /* keep whatever is in the markup */ }
}

$('#destination').addEventListener('change', fillPlaces);

$('#form').addEventListener('submit', async e => {
  e.preventDefault();
  let f = new FormData(e.target), q = Object.fromEntries(f.entries());
  q.days = +q.days; q.travelers = +q.travelers; q.budget = +q.budget; q.interests = f.getAll('interest');
  let b = e.target.querySelector('.primary');
  b.disabled = true; b.textContent = 'Putting your plan together…'; $('#error').textContent = '';
  try {
    let r = await fetch('/api/plan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(q) });
    let d = await r.json();
    if (!r.ok) throw Error(d.detail || 'Could not create plan');
    render(d); $('#results').classList.remove('hidden'); $('#results').scrollIntoView({ behavior: 'smooth' });
  } catch (x) { $('#error').textContent = x.message }
  finally { b.disabled = false; b.innerHTML = 'Plan my trip <b>↗</b>' }
});

function render(d) {
  $('#title').textContent = `${d.days.length} days in ${d.destination}, at your pace.`;
  $('#days').innerHTML = d.days.map(day => `<article class="day"><div class="day-head"><div><span class="day-num">DAY ${String(day.day).padStart(2, '0')}</span><h3>${esc(day.theme)}</h3></div><span class="fit">✓ ${day.validated ? 'Day fits' : 'Check timings'}</span></div>${day.stops.map(s => `<div class="stop"><span class="time">${s.start}</span><div><h4>${esc(s.name)}</h4><p>${esc(s.note)}</p><small>◷ ${s.visit} min &nbsp; · &nbsp; ${s.transit_minutes || 'First'} min transfer &nbsp; · &nbsp; ₹${s.ticket} ticket (demo)</small></div><a target="_blank" rel="noreferrer" href="${s.map_url}">Map ↗</a></div>`).join('')}</article>`).join('');
  let b = d.budget;
  $('#total').textContent = money(b.group_total);
  $('#per').textContent = `${money(b.per_person)} per person · ${d.summary.travelers} travelers` + ` · ${b.assumptions}`;
  $('#costs').innerHTML = Object.entries(b.items).map(([k, v]) => `<div class="cost"><span>${esc(k)}</span><b>${money(v * d.summary.travelers)}</b></div>`).join('');
  $('#budget-note').textContent = b.within_budget ? `Within your ${money(b.target)} group budget by ${money(b.target - b.group_total)}.` : `Estimate exceeds your budget by ${money(b.group_total - b.target)}. Try fewer days or a lower-cost style.`;
}

$('#edit').onclick = () => $('#planner').scrollIntoView({ behavior: 'smooth' });

async function ask() {
  let question = $('#question').value || 'Tell me about this place.';
  $('#answer').textContent = 'Finding a grounded answer…'; $('#source').innerHTML = '';
  try {
    let r = await fetch('/api/guide', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ place: $('#place').value, destination: currentDest(), mode: $('input[name=mode]:checked').value, language: $('[name=language]').value, question })
    });
    let d = await r.json();
    if (!r.ok) throw Error(d.detail);
    $('#answer').innerHTML = `✧ &nbsp;${esc(d.answer)}<small style="display:block;margin:6px 0 0 22px;color:#999">${esc(d.powered_by)}</small>`;
    $('#source').innerHTML = `<a target="_blank" rel="noreferrer" href="${esc(d.source)}">Read the reference ↗</a>`;
  } catch (e) { $('#answer').textContent = e.message || 'Guide unavailable' }
}
$('#ask').onclick = ask;
$('#question').onkeydown = e => { if (e.key === 'Enter') ask() };
$('#mic').onclick = () => {
  let SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { $('#voice-status').textContent = 'Voice recognition is not supported in this browser.'; return }
  let r = new SR(), lang = ({ Hindi: 'hi-IN', Telugu: 'te-IN', Tamil: 'ta-IN', Kannada: 'kn-IN', Bengali: 'bn-IN', Marathi: 'mr-IN' })[$('[name=language]').value] || 'en-IN';
  r.lang = lang;
  r.onstart = () => $('#voice-status').textContent = 'Listening…';
  r.onresult = e => { $('#question').value = e.results[0][0].transcript; $('#voice-status').textContent = 'Got it — tap arrow to ask.' };
  r.onerror = () => $('#voice-status').textContent = 'Could not hear that; try typing.';
  r.start();
};

loadDestinations();
