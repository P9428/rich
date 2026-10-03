"""Paper positions under the contract: 1 SOL size, −10 % stop booked at −15 % or the mark if lower, out at 15 min if not above entry,
half at +100 %, 30 % trail, 24 h time stop."""
import common as C

SIZE_SOL = 1.0
FEE_RT = 0.025
STOP = -0.10
STOP_BOOK = -0.15
FAST_STOP_S = 15 * 60
TAKE_AT = 1.00
TRAIL = 0.30
TIME_STOP_S = 24 * 3600
MAX_OPEN = 5


class Position:
    def __init__(self, mint, symbol, entry, t0, event_id):
        self.mint, self.symbol, self.entry, self.t0, self.event_id = mint, symbol, entry, t0, event_id
        self.peak = entry
        self.remaining = 1.0
        self.realised = 0.0          # fraction-of-size return already booked, before fees
        self.closed = False
        self.fast_checked = False    # the 15-minute look happens once
        self.exits = []

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        p = cls(d["mint"], d["symbol"], d["entry"], d["t0"], d["event_id"])
        p.__dict__.update(d)
        return p

    def _book(self, frac, pct, t, why):
        self.realised += frac * pct
        self.remaining -= frac
        self.exits.append({"t": C.iso(t), "frac": frac, "pct": round(pct, 4), "why": why})
        if self.remaining <= 1e-9:
            self.closed = True

    def mark(self, price, t):
        """Apply one price observation. Returns a list of exits booked on this mark."""
        if self.closed or price <= 0:
            return []
        before = len(self.exits)
        chg = price / self.entry - 1
        if chg <= STOP:
            self._book(self.remaining, min(STOP_BOOK, chg), t, "stop")
            return self.exits[before:]
        if not self.fast_checked and t - self.t0 >= FAST_STOP_S:
            self.fast_checked = True
            if chg <= 0:
                self._book(self.remaining, chg, t, "stale")
                return self.exits[before:]
        if self.remaining == 1.0 and chg >= TAKE_AT:
            self._book(0.5, chg, t, "take-half")
        self.peak = max(self.peak, price)
        if self.remaining < 1.0 and price <= self.peak * (1 - TRAIL):
            self._book(self.remaining, chg, t, "trail")
        elif t - self.t0 >= TIME_STOP_S and not self.closed:
            self._book(self.remaining, chg, t, "time")
        return self.exits[before:]

    def net_sol(self):
        """Realised net in SOL including fees on the booked fraction (open fraction is excluded)."""
        booked = 1.0 - self.remaining
        return SIZE_SOL * (self.realised - FEE_RT * booked)


class Book:
    def __init__(self, state_file, journal_file):
        self.state_file, self.journal_file = state_file, journal_file
        self.open = [Position.from_dict(d) for d in C.load_json(state_file, [])]

    def save(self):
        C.save_json(self.state_file, [p.to_dict() for p in self.open])

    def has(self, mint):
        return any(p.mint == mint for p in self.open)

    def enter(self, mint, symbol, price, t, event_id):
        if self.has(mint) or len(self.open) >= MAX_OPEN or price <= 0:
            return None
        p = Position(mint, symbol, price, t, event_id)
        self.open.append(p)
        C.append(self.journal_file, {"kind": "entry", "mint": mint, "symbol": symbol, "price": price, "event_id": event_id, "size_sol": SIZE_SOL})
        self.save()
        return p

    def mark_all(self, prices, t):
        """prices: {mint: priceUsd}. Books exits, journals closes, drops closed positions."""
        for p in list(self.open):
            if p.mint not in prices:
                continue
            for e in p.mark(prices[p.mint], t):
                C.append(self.journal_file, {"kind": "exit", "mint": p.mint, "symbol": p.symbol, **e})
            if p.closed:
                C.append(self.journal_file, {"kind": "close", "mint": p.mint, "symbol": p.symbol, "entry": p.entry,
                                             "net_sol": round(p.net_sol(), 4), "held_s": int(t - p.t0), "exits": p.exits, "event_id": p.event_id})
                self.open.remove(p)
        self.save()
