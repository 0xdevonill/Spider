// Same-origin proxy to Solana mainnet.
//
// The page prefers this over calling the public node itself. It reads. There
// is no key here and no method that writes. The mint address is base58 and
// case-sensitive, so it is never lowercased.
//
// Pair and creator tax stay as they were. Only the contract and the network
// changed.

const SOL_RPC = process.env.FLY_SOL_RPC || 'https://api.mainnet-beta.solana.com';
const RH_RPC = process.env.FLY_RH_RPC || 'https://rpc.mainnet.chain.robinhood.com';
const TOKEN = process.env.FLY_TOKEN || 'H9Q6v2VGf6t28M46gfdChxNr1JPMhQHVB6C3xb7FAouc';
const WALLET = process.env.FLY_WALLET || '0x6ce4085EfB52a6eBDb7d6989beb8860847f4b42A';
const FEE_ETH = 0.00055;

async function rpc(url, method, params) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
  });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message || 'rpc error');
  return j.result;
}

function mintFacts(info) {
  const parsed = info && info.value && info.value.data && info.value.data.parsed;
  const inf = (parsed && parsed.info) || {};
  const ext = inf.extensions || [];
  let symbol = '';
  for (const e of ext) {
    if (e.extension === 'tokenMetadata' && e.state && e.state.symbol) symbol = e.state.symbol;
  }
  const decimals = inf.decimals == null ? 6 : inf.decimals;
  const supply = inf.supply == null ? null : Number(inf.supply) / 10 ** decimals;
  return { symbol, supply };
}

export default async function handler(req, res) {
  res.setHeader('Cache-Control', 's-maxage=15, stale-while-revalidate=60');
  try {
    const [slot, info, bal] = await Promise.all([
      rpc(SOL_RPC, 'getSlot', []),
      rpc(SOL_RPC, 'getAccountInfo', [TOKEN, { encoding: 'jsonParsed' }]),
      rpc(RH_RPC, 'eth_getBalance', [WALLET, 'latest']).catch(() => null),
    ]);
    const f = mintFacts(info);
    const eth = bal ? parseInt(bal, 16) / 1e18 : null;
    res.status(200).json({
      ok: true,
      block: slot,
      budget_eth: eth,
      launches_left: eth == null ? null : Math.floor(eth / FEE_ETH),
      token: {
        address: TOKEN,
        symbol: f.symbol || 'SPIDER',
        supply: f.supply,
        holders: null,
        transfers: null,
        pair: 'GOOGL',
        creator_tax_pct: 1,
      },
      updated: Math.floor(Date.now() / 1000),
    });
  } catch (e) {
    res.status(200).json({ ok: false, error: String(e.message || e).slice(0, 160) });
  }
}
