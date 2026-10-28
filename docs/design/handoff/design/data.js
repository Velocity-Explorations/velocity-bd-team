(function(){
// Snapshot content (25 Oct 2026) shaped for the redesign artboards.
const TONE = {
  good: { fg: '#80DBA2', bd: '#3A8357', wash: '#182C1F' },
  caution: { fg: '#FAB36D', bd: '#99642A', wash: '#322314' },
  conflict: { fg: '#FFA59D', bd: '#A45953', wash: '#36201E' },
  info: { fg: '#7ECCFF', bd: '#3977A8', wash: '#172836' },
  neutral: { fg: '#BEBEBE', bd: '#555555', wash: '#262626' }
};
const badge = (text, tone, tip) => ({ text, tip: tip || '', ...TONE[tone] });
const VT = { yes: 'good', maybe: 'caution', no: 'conflict', 'not reviewed': 'neutral', 'not yet': 'neutral' };
const vb = v => badge(v, VT[v]);
const SRC = { d: "Set by the call's data", dcg: "Set by the call's data, Claude and Grok", cg: 'Set by Claude and Grok', g: 'Set by Grok', c: 'Set by Claude' };
const DEC = { Pursue: 'good', 'Not relevant': 'neutral', Submitted: 'info', Dismiss: 'neutral', Dismissed: 'neutral' };

function tags(type, typeKey, rest) {
  return [{ text: type, tip: 'Type, ' + SRC[typeKey].replace('Set', 'set') + '.', fg: TONE.info.fg, bd: TONE.info.bd, ring: 'none', src: SRC[typeKey], isType: true }]
    .concat(rest.map(([t, k]) => ({ text: t, tip: SRC[k], src: SRC[k], fg: '#BEBEBE', bd: '#434343', ring: 'none' })));
}
function details(items) {
  return items.map((it, i) => {
    const o = typeof it === 'string' ? { t: it } : it;
    return { t: o.t, tip: o.tip || '', sep: i < items.length - 1 ? '·' : '', tab: o.tip ? 0 : -1, color: o.link ? '#F5F5F5' : '#BEBEBE', deco: o.tip ? 'underline dotted' : (o.link ? 'underline' : 'none') };
  });
}
function due(main, o = {}) {
  const word = !!o.word;
  return { main, time: o.time || '', sub: o.sub || '', tip: o.tip || '', tab: o.tip ? 0 : -1, color: word ? '#BEBEBE' : '#F5F5F5', deco: o.tip ? 'underline dotted' : 'none' };
}
function sources(r) {
  const out = [];
  if (r.due.tip) out.push({ k: 'Due', v: r.due.tip });
  r.details.filter(d => d.tip).forEach(d => out.push({ k: d.t, v: d.tip }));
  r.badges.filter(b => b.tip).forEach(b => out.push({ k: b.text, v: b.tip }));
  const type = r.tags.find(t => t.isType);
  if (type) out.push({ k: 'Type: ' + type.text, v: type.src });
  const groups = {};
  r.tags.filter(t => !t.isType).forEach(t => { (groups[t.src] = groups[t.src] || []).push(t.text); });
  Object.entries(groups).forEach(([src, names]) => out.push({ k: names.join(', '), v: src }));
  return out;
}
function qrow(o) {
  const r = {
    title: o.title,
    judges: [{ who: 'Claude', b: vb(o.c), why: true, label: "Claude's and Grok's reasons", bd: '#434343', ink: o.open ? '#FFCB03' : '#F5F5F5' }, { who: 'Grok', b: vb(o.g), why: true, label: "Claude's and Grok's reasons", bd: '#434343', ink: o.open ? '#FFCB03' : '#F5F5F5' }],
    claudeReason: o.reason,
    flag: o.flag || null,
    details: details(o.details),
    badges: o.badges || [],
    tags: o.tags,
    due: o.due,
    reason: o.reason,
    grok: o.grok,
    firstDate: '2026-10-24', firstTime: o.first + ' MDT',
    decided: (o.decided || []).map(([who, word]) => ({ who, word, fg: TONE[DEC[word]].fg })),
    open: !!o.open, openAttr: o.open ? 'true' : 'false', whyLabel: o.open ? 'hide why' : 'why',
    noteOpen: !!o.noteOpen, noteClosed: !o.noteOpen,
    menuOpen: !!o.menu, menuClosed: !o.menu,
    people: (o.decided || []).map(([who, word, note, when]) => ({ who, b: badge(word, DEC[word]), note: note || '', hasNote: !!note, when: when || '', noteAttr: o.notesOpen ? 'true' : 'false', bd: '#434343', ink: o.notesOpen ? '#FFCB03' : '#F5F5F5' })),
    notesOpen: !!o.notesOpen,
    selected: !!o.selected,
    tipOpen: o.tipOpen || ''
  };
  r.noDecided = r.decided.length === 0;
  r.hasBadges = r.badges.length > 0;
  r.notes = r.people.filter(p => p.note);
  r.noteCount = r.notes.length === 1 ? '1 note' : r.notes.length + ' notes';
  const yes = r.decided.some(d => d.word === 'Pursue' || d.word === 'Submitted'), no = r.decided.some(d => d.word === 'Not relevant' || d.word === 'Dismiss');
  r.peopleFlag = yes && no ? badge('people disagree', 'conflict') : null;
  r.sources = sources(r);
  if (o.ringTag) r.tags = r.tags.map(t => t.text === o.ringTag ? { ...t, ring: '2px solid #FFCB03' } : t);
  return r;
}

const DISAGREE = badge('judges disagree', 'caution');
const MEMBER_DUE = 'Member-only page: sign in to NSTXL to see the deadline.';

const Q = {
  tacfi: {
    title: 'PY26.2 TACFI Notice of Opportunity', c: 'maybe', g: 'maybe',
    details: ['SpaceWERX', 'TACFI', 'U.S. Space Force'],
    tags: tags('SBIR or STTR', 'dcg', [['Space', 'cg'], ['USSF', 'dcg'], ['Phase II holders only', 'dcg']]),
    due: due('no close date', { word: true, tip: 'No close date on the Get Funded page (TBD, or submissions on a continuous basis).' }),
    reason: "The notice gives no technical scope, so Velocity's fit can't be judged, and eligibility depends on whether Velocity holds a current or recent SBIR/STTR Phase II award, which the description doesn't confirm.",
    grok: 'This is a SpaceWERX TACFI funding notice with no defined technical scope, and eligibility requires a current or recent Phase II that is not established here, so fit with Velocity’s software/AI work cannot be confirmed.',
    first: '05:49'
  },
  cmd: {
    title: 'Cross Mission Data (CMD) Industry Design Sprint', c: 'maybe', g: 'maybe',
    details: ['NSTXL', 'OTA opportunity', 'SpEC'],
    tags: tags('OTA', 'dcg', [['Space', 'cg'], ['Data and analytics', 'cg'], ['USSF', 'dcg'], ['Members only', 'dcg']]),
    due: due('members only', { word: true, tip: MEMBER_DUE }),
    reason: "The description is member-only and unreadable, and the title suggests cross-mission data integration work that could fit Velocity's software and data platform capabilities, but \"design sprint\" could also mean a workshop or event format that Velocity doesn't pursue.",
    grok: 'The member-only description is unavailable, and while Cross Mission Data work could fit Velocity’s software, analytics, and C2 focus, an Industry Design Sprint may be event participation rather than a development effort.',
    first: '05:43', noteOpen: true
  },
  c2: {
    title: 'Command and Control (C2) Capability Prototype (C2 Capability) | Project No. 26-08', c: 'yes', g: 'yes',
    details: ['NSTXL', 'OTA opportunity', 'SpEC'],
    tags: tags('OTA', 'dcg', [['C2', 'cg'], ['Space', 'g'], ['USSF', 'dcg'], ['Members only', 'dcg']]),
    due: due('members only', { word: true, tip: MEMBER_DUE }),
    reason: "The title is a Command and Control capability prototype through the SpEC OTA consortium, which matches Velocity's flagship Echo C2 work and its eligibility for SpEC opportunities, though the member-only description could not be read to confirm scope.",
    grok: "This SpEC OTA for a Command and Control capability prototype matches Velocity's flagship Echo C2 software work and prior pursuit of similar C2 opportunities.",
    first: '05:43', decided: [['Analyst A', 'Pursue', 'Fits our C2 work; ask NSTXL for the member page', '2026-10-24 11:07 MDT']]
  },
  gps: {
    title: 'GPS Gen4 Ground | Project 26-18', c: 'maybe', g: 'maybe',
    details: ['NSTXL', 'SpEC'],
    tags: tags('White paper', 'dcg', [['Software', 'cg'], ['Hardware', 'g'], ['C2', 'cg'], ['Space', 'cg'], ['Communications', 'g'], ['USSF', 'dcg']]),
    due: due('2026-10-30', { sub: '5 days left' }),
    reason: "The GPS Gen4 Ground white paper asks for architecture and acquisition ideas across unspecified developmental swim lanes, and the description doesn't show whether the scope is primarily ground software (a potential fit for Velocity's software and legacy modernization work) or hardware and facilities, which Velocity doesn't do, so the CUI guidebook would need to be reviewed before deciding.",
    grok: 'GPS Gen4 Ground is a vague SpEC acquisition-shaping white paper that could include C2 or ground-software swim lanes aligned with Velocity, but the posting does not confirm software, AI/ML, or legacy-modernization work versus specialized GPS ground hardware.',
    first: '05:42'
  },
  lunar: {
    title: 'Lunar Surface C&PNT architecture for an Integrated Lunar Surface Network', c: 'maybe', g: 'no', flag: DISAGREE,
    details: ['NASA Forecast', 'NASA GRC', 'set-aside to be determined', 'NAICS 541715', { t: 'solicitation FY2026', tip: 'Award expected FY2026' }, { t: '$251K - $500K', tip: 'Estimated contract value' }, 'Watts, Robert E. (SSC-BA111)', { t: 'GRC-smallbusiness@mail.nasa.gov', link: true, tip: "Listed with Watts, Robert E. (SSC-BA111), though the address looks like someone else's" }],
    tags: tags('Forecast', 'dcg', [['Space', 'cg'], ['Communications', 'cg'], ['NASA', 'dcg']]),
    due: due('forecast', { word: true, sub: 'FY2026', tip: 'A forecast: NASA expects to release the solicitation in FY2026.' }),
    reason: "The work is a concept study for lunar communications, navigation, and timing architecture, which could involve network and software architecture that Velocity might address, but its emphasis on space-domain physical systems and NASA GRC's R&D focus makes the fit to Velocity's software, AI/ML, and C2 core uncertain.",
    grok: 'This is a NASA lunar surface communications, positioning, navigation, and timing architecture and acquisition study, not software, AI/ML, C2 tool, or legacy-modernization work within Velocity’s scope.',
    first: '05:32'
  },
  isrds: {
    title: 'INTELLIGENT SYSTEMS RESEARCH AND DEVELOPMENT SUPPORT (ISRDS-4)', c: 'yes', g: 'yes',
    details: ['NASA Forecast', 'NASA ARC', 'set-aside to be determined', 'NAICS 541715', { t: 'solicitation Q3 FY2026', tip: 'Award expected Q2 FY2028' }, { t: '$250M - $500M', tip: 'Estimated contract value' }, { t: 'Kobayashi, Linda T. (ARC-TI)', link: true, tip: 'linda.t.kobayashi@nasa.gov' }],
    tags: tags('Forecast', 'dcg', [['Software', 'cg'], ['Hardware', 'g'], ['AI and ML', 'cg'], ['Autonomy', 'cg'], ['Communications', 'g'], ['Data and analytics', 'cg'], ['Services', 'cg'], ['NASA', 'dcg']]),
    due: due('forecast', { word: true, sub: 'Q3 FY2026', tip: 'A forecast: NASA expects to release the solicitation in Q3 FY2026.' }),
    reason: "ISRDS-4 is a NASA R&D support contract covering AI, knowledge-based systems, software verification and validation, and autonomous control, which closely matches Velocity's AI/ML, autonomy, and software work, though its $250M to $500M scale will likely require teaming as a small business.",
    grok: 'The forecast centers on AI, autonomy, decision support, knowledge discovery, and software V&V R&D, which matches Velocity’s AI/ML and autonomous-systems software work despite a secondary hardware element.',
    first: '05:31'
  },
  swap: {
    title: 'Suitable Warfighting Adaptive Payloads (SWAP)-USV Sprint 2', c: 'maybe', g: 'no', flag: DISAGREE,
    details: ['DIU', 'Challenge', 'Defense Innovation Unit'],
    tags: tags('Prize challenge', 'dcg', [['Hardware', 'cg'], ['Autonomy', 'cg'], ['C2', 'cg'], ['ISR', 'cg'], ['Navy', 'g'], ['DIU', 'dcg'], ['OSD', 'c']]),
    due: due('2026-11-30', { time: '21:59 MST', sub: '36 days left', tip: 'DIU gives 2026-11-30T23:59:59-05:00, shown here in America/Denver.' }),
    reason: "The core of this prize challenge is fielding mature USVs and hard-kill effectors, which are hardware areas Velocity does not pursue, but the interoperable C2 architecture and sensor integration work could fit Velocity's Echo C2 and software capabilities if pursued as a software partner.",
    grok: "Sprint 2 requires production-ready USVs and hard-kill counter-air effectors for fielding, which is hardware manufacturing outside Velocity's software, AI/ML, and C2 scope.",
    first: '05:30', open: true
  },
  sttr: {
    title: 'DOW STTR SPECIFIC TOPIC 27.TZ Release 1', c: 'maybe', g: 'maybe',
    details: ['AFWERX', 'STTR cycle', 'Department of the Air Force'],
    badges: [badge('Air Force', 'info', 'Includes U.S. Air Force topics'), badge('opens 28 Oct', 'caution', 'Pre-release from 7 Oct; submissions open 28 Oct')],
    tags: tags('SBIR or STTR', 'dcg', [['USAF', 'dcg'], ['Small business set-aside', 'cg']]),
    due: due('2026-11-25', { sub: '31 days left' }),
    reason: 'This is an unspecified DoD STTR cycle with no visible topics (topics are only on DSIP, which the scanner cannot read), so Velocity cannot tell whether any topic matches its software, AI/ML, or C2 work, though the Air Force STTR pathway itself fits its SBIR/STTR experience and should be checked on DSIP before the November 25, 2026 close.',
    grok: 'This is an Air Force STTR cycle Velocity’s funding model fits, but the specific topics live only on DSIP and are not described, so fit with software, AI/ML, or C2 work cannot be confirmed.',
    first: '05:29', decided: [['Analyst A', 'Pursue', 'Check the AF topics on DSIP', '2026-10-24 11:14 MDT'], ['Analyst B', 'Not relevant', 'Topics look hardware heavy', '2026-10-24 11:21 MDT']]
  },
  sbir: {
    title: 'DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1', c: 'maybe', g: 'maybe',
    details: ['AFWERX', 'SBIR cycle', 'Department of the Air Force'],
    badges: [badge('Air Force', 'info', 'Includes U.S. Air Force topics'), badge('opens 28 Oct', 'caution', 'Pre-release from 7 Oct; submissions open 28 Oct')],
    tags: tags('SBIR or STTR', 'dcg', [['USAF', 'dcg'], ['Small business set-aside', 'cg']]),
    due: due('2026-11-25', { sub: '31 days left' }),
    reason: "This is an SBIR solicitation cycle with Air Force topics that could plausibly include software or AI/ML work matching Velocity's capabilities, but the topics themselves are only listed on DSIP, which the scanner cannot read, so relevance cannot be determined without reviewing the specific topics.",
    grok: 'This is an Air Force/AFWERX SBIR cycle Velocity is set up to pursue, but the specific 27.BZ and 27.BX topic content is not available, so relevance to software, AI/ML, C2, or legacy modernization cannot be confirmed.',
    first: '05:29'
  }
};

const queueRows = ['tacfi', 'cmd', 'c2', 'gps', 'lunar', 'isrds', 'swap', 'sbir'].map(k => qrow(k === 'isrds' ? { ...Q[k], menu: true } : Q[k]));
const queueRowsNarrow = ['tacfi', 'cmd', 'c2', 'lunar', 'swap', 'sbir'].map(k => qrow({ ...Q[k], noteOpen: false }));
const enlargedRow = [qrow({ ...Q.lunar, open: true, ringTag: 'Communications', tipOpen: 'Communications: set by Claude and Grok' })];

// All calls
function crow(o) {
  const judges = o.judges.map(([who, v, why, open]) => ({ who, b: vb(v), why: why || '', hasWhy: !!why, open: !!open, whyLabel: open ? 'hide why' : 'why' }));
  const dec = o.decision;
  return {
    title: o.title, details: details(o.details), badges: o.badges || [], hasBadges: !!(o.badges || []).length, tags: o.tags,
    filter: badge(o.filter[0], o.filter[0] === 'kept' ? 'good' : (o.filter[0] === 'rejected' ? 'neutral' : 'caution')),
    filterTier: o.filter[1] || '', filterReason: o.filter[2] || '',
    judges, flag: o.flag || null,
    decBadge: dec.status ? badge(dec.status, DEC[dec.statusKey] || 'neutral') : badge('undecided', 'neutral'),
    decLines: (dec.lines || []).map(([who, word, when]) => ({ who, word, when, fg: TONE[DEC[word]].fg })),
    decSingle: dec.by ? { who: dec.by, when: dec.when } : null,
    peopleFlag: dec.people ? badge('people disagree', 'conflict') : null,
    control: dec.control, controlOpen: !!dec.open, controlClosed: !dec.open,
    controlCurrent: dec.current || 'Choose',
    notes: (o.notes || []).map(([text, by]) => ({ text, by })), noNotes: !(o.notes || []).length,
    due: o.due, firstDate: '2026-10-24', firstTime: o.first + ' MDT'
  };
}
const callsRows = [
  crow({
    title: 'Silicon Valley Space Week', details: ['SSC Front Door', '1401 N Shoreline Blvd Mountain View, CA 94043'],
    tags: tags('Event', 'd', [['USSF', 'd']]), filter: ['rejected', '', 'no keyword match'],
    judges: [['Claude', 'not reviewed'], ['Grok', 'not yet']], decision: { control: 'decide' },
    due: due('29 OCT 2026 : 16:00 PDT', { sub: '4 days left' }), first: '05:49'
  }),
  crow({
    title: 'Global MilSatCom 2026', details: ['SSC Front Door', 'London, United Kingdom'],
    tags: tags('Event', 'dcg', [['Space', 'cg'], ['Communications', 'cg'], ['USSF', 'dcg']]), filter: ['kept', 'broad tier'],
    judges: [['Claude', 'maybe', "The event covers military satellite communications, which is only partly aligned with Velocity's software, C2, and network-management work, since the topic is dominated by space and hardware systems.", true], ['Grok', 'no', "Military satellite communications is a space and communications-systems topic outside Velocity's software, AI/ML, C2, NLP, and legacy-modernization work, so attending would not help find or win related contracts."]],
    flag: DISAGREE,
    decision: { status: 'dismissed', statusKey: 'Dismissed', by: 'Analyst B', when: '2026-10-24 11:28 MDT', control: 'change' },
    due: due('06 NOV 2026 : 17:00 GMT', { sub: '12 days left' }), first: '05:49'
  }),
  crow({
    title: Q.c2.title, details: ['NSTXL', 'OTA opportunity', 'SpEC'], tags: Q.c2.tags, filter: ['kept', 'tight tier'],
    judges: [['Claude', 'yes', Q.c2.reason], ['Grok', 'yes', Q.c2.grok]],
    decision: { status: 'pursue', statusKey: 'Pursue', by: 'Analyst A', when: '2026-10-24 11:07 MDT', control: 'add yours' },
    notes: [['Fits our C2 work; ask NSTXL for the member page', 'Analyst A, 2026-10-24 11:07 MDT']],
    due: due('members only', { word: true, tip: MEMBER_DUE }), first: '05:43'
  }),
  crow({
    title: 'Facilities Operations and Maintenance Services (FOMS)',
    details: ['NASA Forecast', 'NASA AFRC', 'set-aside to be determined', 'NAICS 561210', { t: 'solicitation Q1 FY2027', tip: 'Award expected Q2 FY2027' }, { t: '$20.1M - $50M', tip: 'Estimated contract value' }, { t: 'Werner, Brandon J. (AFRC-221)', link: true, tip: 'brandon.werner-1@nasa.gov' }],
    tags: tags('Forecast', 'd', [['NASA', 'd']]), filter: ['rejected', '', 'blocklist: \\brepair\\b'],
    judges: [['Claude', 'not reviewed'], ['Grok', 'not yet']], decision: { control: 'decide' },
    due: due('forecast', { word: true, sub: 'Q1 FY2027', tip: 'A forecast: NASA expects to release the solicitation in Q1 FY2027.' }), first: '05:32'
  }),
  crow({
    title: 'Improved Mobile Electric Power Distribution System', details: ['DIU', 'CSO', 'Defense Innovation Unit'],
    tags: tags('White paper', 'dcg', [['Hardware', 'cg'], ['Test and evaluation', 'c'], ['USMC', 'cg'], ['DIU', 'dcg']]), filter: ['kept', 'broad tier'],
    judges: [['Claude', 'no', "This is a hardware-centric power distribution panel project requiring physical electrical equipment development and MIL-STD compliance testing, which falls outside Velocity's software, AI/ML, and C2 focus and its stated exclusion of hardware development and manufacturing."], ['Grok', 'no', 'This is a hardware prototyping effort for tactical electrical power distribution panels and generators, which falls outside Velocity’s software, AI/ML, and C2 focus and matches work they explicitly do not do.']],
    decision: { status: 'not relevant', statusKey: 'Not relevant', by: 'Analyst A', when: '2026-10-24 11:35 MDT', control: 'add yours' },
    notes: [['Power hardware, not our lane', 'Analyst A, 2026-10-24 11:35 MDT']],
    due: due('2026-10-28', { time: '21:59 MDT', sub: '3 days left' }), first: '05:30'
  }),
  crow({
    title: 'DOW STTR SPECIFIC TOPIC 27.TZ Release 1', details: ['AFWERX', 'STTR cycle', 'Department of the Air Force'],
    badges: Q.sbir.badges, tags: Q.sbir.tags, filter: ['kept', 'broad tier'],
    judges: [['Claude', 'maybe', 'This is an unspecified DoD STTR cycle with no visible topics (topics are only on DSIP, which the scanner cannot read), so Velocity cannot tell whether any topic matches its software, AI/ML, or C2 work, though the Air Force STTR pathway itself fits its SBIR/STTR experience and should be checked on DSIP before the November 25, 2026 close.'], ['Grok', 'maybe', 'This is an Air Force STTR cycle Velocity’s funding model fits, but the specific topics live only on DSIP and are not described, so fit with software, AI/ML, or C2 work cannot be confirmed.']],
    decision: { status: 'pursue', statusKey: 'Pursue', people: true, lines: [['Analyst A', 'Pursue', '2026-10-24 11:14 MDT'], ['Analyst B', 'Not relevant', '2026-10-24 11:21 MDT']], control: 'change', open: true, current: 'Not relevant' },
    notes: [['Check the AF topics on DSIP', 'Analyst A, 2026-10-24 11:14 MDT'], ['Topics look hardware heavy', 'Analyst B, 2026-10-24 11:21 MDT']],
    due: due('2026-11-25', { sub: '31 days left' }), first: '05:29'
  })
];


// Turn 2: vote and decide options
function vrow(o, st = {}) {
  const base = qrow(o);
  return { ...base,
    menuOpen: !!st.menu, menuClosed: !st.menu, noteOpen: !!st.note, noteClosed: !st.note,
    open: false, openAttr: 'false', whyLabel: 'why', tipOpen: '' };
}
const optA = [vrow(Q.tacfi), vrow(Q.c2, { note: true }), vrow(Q.swap, { menu: true })];
const optANote = [qrow(Q.c2)];
const turn3a = [qrow(Q.tacfi), qrow({ ...Q.sttr, notesOpen: true }), qrow({ ...Q.swap, open: false })];
const turn3b = [qrow(Q.tacfi), qrow({ ...Q.sttr, selected: true }), qrow({ ...Q.swap, open: false })];
const sttrNotes = qrow(Q.sttr).notes;
const optB = [vrow(Q.tacfi), vrow(Q.c2), vrow(Q.swap, { menu: true })];
const optC = [vrow(Q.tacfi), vrow(Q.c2, { note: true }), vrow(Q.swap, { menu: true })];
const decideMenu = ['Pursue', 'Not relevant', 'Submitted', 'Dismiss'].map((w, i) => ({ word: w, fg: TONE[DEC[w]].fg, bg: i === 0 ? '#333333' : 'transparent' }));
window.BD = { turn3a, turn3b, sttrNotes, optANote, optA, optB, optC, decideMenu,  TONE, badge, vb, queueRows, queueRowsNarrow, enlargedRow, callsRows };

})();
