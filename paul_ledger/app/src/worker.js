// Paul's Book — Cloudflare Worker: serves the app + a token-gated JSON API on D1.
const enc = new TextEncoder();
const b64u = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
const b64uToBuf = s => { s=s.replace(/-/g,'+').replace(/_/g,'/'); const bin=atob(s); const a=new Uint8Array(bin.length); for(let i=0;i<bin.length;i++)a[i]=bin.charCodeAt(i); return a; };
const json = (data, status=200) => new Response(JSON.stringify(data), {status, headers:{'content-type':'application/json'}});

async function hmacKey(secret){ return crypto.subtle.importKey('raw', enc.encode(secret), {name:'HMAC',hash:'SHA-256'}, false, ['sign','verify']); }
async function sign(payload, secret){
  const body = b64u(enc.encode(JSON.stringify(payload)));
  const key = await hmacKey(secret);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(body));
  return body + '.' + b64u(sig);
}
async function verifyToken(token, secret){
  if(!token || token.indexOf('.')<0) return null;
  const [body, sig] = token.split('.');
  const key = await hmacKey(secret);
  const ok = await crypto.subtle.verify('HMAC', key, b64uToBuf(sig), enc.encode(body));
  if(!ok) return null;
  try { return JSON.parse(new TextDecoder().decode(b64uToBuf(body))); } catch(e){ return null; }
}
function randCode(n=6){ const a='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; let s=''; const r=crypto.getRandomValues(new Uint8Array(n)); for(let i=0;i<n;i++)s+=a[r[i]%a.length]; return s; }

// resolve the caller: returns {code, admin} or null
async function auth(req, env){
  const secret = env.AUTH_SECRET || 'dev-secret';
  const h = req.headers.get('authorization') || '';
  const token = h.startsWith('Bearer ') ? h.slice(7) : '';
  const p = await verifyToken(token, secret);
  if(!p || !p.c) return null;
  const row = await env.DB.prepare('SELECT is_admin,revoked FROM codes WHERE code=?').bind(p.c).first();
  if(!row || row.revoked) return null;
  return { code:p.c, admin: !!row.is_admin };
}

export default {
  async fetch(req, env){
    const url = new URL(req.url);
    const path = url.pathname;
    if(!path.startsWith('/api/')) return env.ASSETS.fetch(req);
    const secret = env.AUTH_SECRET || 'dev-secret';

    try {
      // --- login ---
      if(path==='/api/login' && req.method==='POST'){
        const {code} = await req.json();
        if(!code) return json({error:'no code'},400);
        const row = await env.DB.prepare('SELECT code,is_admin,revoked FROM codes WHERE code=?').bind(String(code).trim().toUpperCase()).first();
        if(!row || row.revoked) return json({error:'invalid code'},401);
        const token = await sign({c:row.code, admin:row.is_admin?1:0, iat:Date.now()}, secret);
        return json({token, admin: !!row.is_admin});
      }

      const me = await auth(req, env);
      if(!me) return json({error:'unauthorized'},401);

      // --- state ---
      if(path==='/api/state' && req.method==='GET'){
        const row = await env.DB.prepare("SELECT value,updated FROM kv WHERE key='state'").first();
        return json({ state: row? JSON.parse(row.value): null, updated: row? row.updated: 0, me:{admin:me.admin} });
      }
      if(path==='/api/state' && req.method==='PUT'){
        const {state, base} = await req.json();
        const cur = await env.DB.prepare("SELECT updated FROM kv WHERE key='state'").first();
        if(cur && base!=null && cur.updated!==base){
          const row = await env.DB.prepare("SELECT value,updated FROM kv WHERE key='state'").first();
          return json({conflict:true, state: JSON.parse(row.value), updated: row.updated},409);
        }
        const now = Date.now();
        await env.DB.prepare("INSERT INTO kv(key,value,updated) VALUES('state',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated")
          .bind(JSON.stringify(state), now).run();
        return json({ok:true, updated:now});
      }

      // --- live FX (USD->RON, AED->RON), cached in D1 for 6h ---
      if(path==='/api/fx' && req.method==='GET'){
        const row = await env.DB.prepare("SELECT value,updated FROM kv WHERE key='fx'").first();
        const fresh = row && (Date.now()-row.updated) < 6*3600*1000;
        if(fresh) return json({...JSON.parse(row.value), updated:row.updated, cached:true});
        try{
          const r = await fetch('https://open.er-api.com/v6/latest/USD');
          const d = await r.json();
          if(d && d.rates && d.rates.RON && d.rates.AED){
            const fx = { usd_ron: d.rates.RON, aed_ron: d.rates.RON/d.rates.AED, chf_ron: d.rates.CHF? d.rates.RON/d.rates.CHF : null, eur_ron: d.rates.EUR? d.rates.RON/d.rates.EUR : null, source:'open.er-api.com' };
            const now = Date.now();
            await env.DB.prepare("INSERT INTO kv(key,value,updated) VALUES('fx',?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated=excluded.updated")
              .bind(JSON.stringify(fx), now).run();
            return json({...fx, updated:now, cached:false});
          }
        }catch(e){ /* fall through to stale/fallback */ }
        if(row) return json({...JSON.parse(row.value), updated:row.updated, cached:true, stale:true});
        return json({usd_ron:4.55, aed_ron:1.24, chf_ron:5.1, eur_ron:5.25, source:'fallback', updated:0, fallback:true});
      }

      // --- codes (admin only) ---
      if(path==='/api/codes'){
        if(!me.admin) return json({error:'admin only'},403);
        if(req.method==='GET'){
          const rows = await env.DB.prepare('SELECT code,label,is_admin,revoked,created FROM codes ORDER BY created DESC').all();
          return json({codes: rows.results});
        }
        if(req.method==='POST'){
          const {label} = await req.json();
          let code; for(let i=0;i<5;i++){ code=randCode(6); const ex=await env.DB.prepare('SELECT code FROM codes WHERE code=?').bind(code).first(); if(!ex) break; }
          await env.DB.prepare('INSERT INTO codes(code,label,is_admin,revoked,created) VALUES(?,?,0,0,?)').bind(code, label||'', Date.now()).run();
          return json({code, label:label||''});
        }
      }
      if(path==='/api/codes/revoke' && req.method==='POST'){
        if(!me.admin) return json({error:'admin only'},403);
        const {code} = await req.json();
        await env.DB.prepare('UPDATE codes SET revoked=1 WHERE code=? AND is_admin=0').bind(String(code).toUpperCase()).run();
        return json({ok:true});
      }

      return json({error:'not found'},404);
    } catch(e){
      return json({error:String(e && e.message || e)},500);
    }
  }
};
