using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using cAlgo.API;
using cAlgo.API.Internals;

/*
 * StockMarketBot — cTrader cBot
 * Legge stock_signals.json dal bridge e apre posizioni long con SL e TP.
 *
 * ISOLAMENTO: usa label prefix "SMB_" — non tocca mai trade TRFX_* o GRID_*
 * ACCOUNT:    da agganciare SOLO sul conto DEMO FPMarkets
 *
 * Setup:
 *   1. Copia questo file nel cBot editor di cTrader
 *   2. Aggancialo a qualsiasi simbolo (es. EURUSD) sul conto DEMO
 *   3. Il Python script scrive i segnali; questo bot li legge ogni 60s
 */

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class StockMarketBot : Robot
    {
        [Parameter("Bridge File Path", Group = "Bridge",
            DefaultValue = @"C:\TradeBridge\StockBot\stock_signals.json")]
        public string BridgePath { get; set; }

        [Parameter("Trade Size % of Balance", Group = "Risk",
            DefaultValue = 2.5, MinValue = 0.5, MaxValue = 10.0)]
        public double TradeSizePct { get; set; }

        [Parameter("Segnali per Settimana", Group = "Risk",
            DefaultValue = 3, MinValue = 1, MaxValue = 10)]
        public int SignalsPerWeek { get; set; }

        [Parameter("Check Interval (secondi)", Group = "Timing",
            DefaultValue = 60, MinValue = 10, MaxValue = 300)]
        public int CheckIntervalSec { get; set; }

        // -----------------------------------------------------------------------
        private const string LABEL_PREFIX = "SMB_";
        private string _lastProcessedWeek = "";

        // Anti-spam: traccia l'ultima volta che abbiamo loggato "MarketClosed" per ogni simbolo
        // Chiave: yfSymbol, Valore: ora UTC dell'ultimo log
        private readonly Dictionary<string, DateTime> _lastMarketClosedLog = new Dictionary<string, DateTime>();

        // Intervallo minimo tra due log MarketClosed per lo stesso simbolo (30 minuti)
        private const int MARKET_CLOSED_LOG_INTERVAL_MIN = 30;

        // Storico trade: ignora tutto prima di questa data (pulizia slate)
        private static readonly DateTime HISTORY_START_UTC = new DateTime(2026, 5, 22, 0, 0, 0, DateTimeKind.Utc);

        // -----------------------------------------------------------------------
        protected override void OnStart()
        {
            Timer.Start(CheckIntervalSec);
            Positions.Closed += OnPositionClosed;

            // Forza la subscription di tutti i simboli già aperti (bot + manuali)
            // senza questo, pos.CurrentPrice fallisce per simboli non sottoscritti
            foreach (var pos in Positions)
            {
                try { Symbols.GetSymbol(pos.SymbolName); }
                catch { }
            }

            // Sottoscrive automaticamente ogni nuova posizione aperta dopo l'avvio
            Positions.Opened += (args) =>
            {
                try { Symbols.GetSymbol(args.Position.SymbolName); }
                catch { }
            };

            Print($"[SMB] Avviato. Bridge: {BridgePath}");
            Print($"[SMB] Trade size: {TradeSizePct}% | Segnali/settimana: {SignalsPerWeek}");
            // Primo check immediato
            CheckSignals();
            WritePortfolioStatus();
        }

        protected override void OnTimer()
        {
            CheckSignals();
            WritePortfolioStatus();
        }

        private void OnPositionClosed(PositionClosedEventArgs args)
        {
            if (args.Position.Label != null && args.Position.Label.StartsWith(LABEL_PREFIX))
                WritePortfolioStatus();
        }

        // -----------------------------------------------------------------------
        private void CheckSignals()
        {
            if (!System.IO.File.Exists(BridgePath))
            {
                Print($"[SMB] File non trovato: {BridgePath}");
                return;
            }

            SignalFile signals;
            try
            {
                string json = System.IO.File.ReadAllText(BridgePath);
                signals = JsonSerializer.Deserialize<SignalFile>(json,
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            }
            catch (Exception ex)
            {
                Print($"[SMB] Errore parsing JSON: {ex.Message}");
                return;
            }

            if (signals == null || string.IsNullOrEmpty(signals.Week))
                return;

            if (signals.Signals == null || signals.Signals.Count == 0)
            {
                _lastProcessedWeek = signals.Week;
                Print("[SMB] Nessun segnale questa settimana.");
                return;
            }

            // Settimana già processata → skip (a meno che ci siano ancora segnali da aprire)
            if (signals.Week == _lastProcessedWeek && CountWeekSignalsOpened(signals) >= Math.Min(SignalsPerWeek, signals.Signals.Count))
                return;

            // Nuova settimana → logga
            if (signals.Week != _lastProcessedWeek)
            {
                Print($"[SMB] Nuovi segnali — settimana {signals.Week} ({signals.GeneratedAt})");
                _lastProcessedWeek = signals.Week;
            }

            int opened = 0;
            foreach (var signal in signals.Signals)
            {
                if (opened >= SignalsPerWeek)
                    break;

                if (IsAlreadyOpen(signal.YfSymbol))
                {
                    opened++; // conta come già aperto questa settimana
                    continue;
                }

                bool success = OpenTrade(signal);
                if (success) opened++;
            }

            Print($"[SMB] Trade settimana {signals.Week}: {opened}/{SignalsPerWeek}");
        }

        // -----------------------------------------------------------------------
        private bool OpenTrade(SignalData signal)
        {
            // Trova il simbolo su cTrader
            var sym = Symbols.GetSymbol(signal.CtSymbol);
            if (sym == null)
            {
                Print($"[SMB] Simbolo non trovato su cTrader: {signal.CtSymbol} (skip)");
                return false;
            }

            double ask = sym.Ask;
            if (ask <= 0)
            {
                Print($"[SMB] {signal.CtSymbol}: prezzo non disponibile.");
                return false;
            }

            // Calcola volume in base al rischio: se SL colpito → perdita = TradeSizePct% del saldo
            double volume = CalculateVolume(sym, ask, signal.SlPct);
            if (volume <= 0)
            {
                Print($"[SMB] {signal.CtSymbol}: volume non valido.");
                return false;
            }

            // SL e TP come prezzi assoluti (evita problemi con PipSize variabile)
            double slPrice = ask * (1.0 - signal.SlPct / 100.0);
            double tpPrice = ask * (1.0 + signal.TpPct / 100.0);

            string label = LABEL_PREFIX + signal.YfSymbol;

            // Apri ordine senza SL/TP, poi imposta prezzi assoluti
            var result = ExecuteMarketOrder(
                TradeType.Buy,
                sym.Name,
                volume,
                label
            );

            if (result.IsSuccessful)
            {
                ModifyPosition(result.Position, slPrice, tpPrice, ProtectionType.Absolute);
                // Reset anti-spam in caso di successo futuro
                _lastMarketClosedLog.Remove(signal.YfSymbol);
                Print($"[SMB] OK {signal.YfSymbol} ({signal.CtSymbol}) " +
                      $"entry={ask:F4} vol={volume} " +
                      $"SL={slPrice:F4} (-{signal.SlPct:F2}%) " +
                      $"TP={tpPrice:F4} (+{signal.TpPct:F2}%) " +
                      $"score={signal.Score}");
                return true;
            }
            else if (result.Error == ErrorCode.MarketClosed || result.Error == ErrorCode.TechnicalError)
            {
                // Anti-spam: logga al massimo ogni 30 minuti per simbolo
                DateTime now = DateTime.UtcNow;
                bool shouldLog = !_lastMarketClosedLog.TryGetValue(signal.YfSymbol, out DateTime lastLog)
                                 || (now - lastLog).TotalMinutes >= MARKET_CLOSED_LOG_INTERVAL_MIN;
                if (shouldLog)
                {
                    _lastMarketClosedLog[signal.YfSymbol] = now;
                    string reason = result.Error == ErrorCode.MarketClosed ? "mercato chiuso" : "errore tecnico";
                    Print($"[SMB] {signal.YfSymbol}: {reason}, riprovo ogni {MARKET_CLOSED_LOG_INTERVAL_MIN}min");
                }
                return false;
            }
            else
            {
                Print($"[SMB] X {signal.YfSymbol}: ordine fallito — {result.Error}");
                return false;
            }
        }

        // -----------------------------------------------------------------------
        // slPct = stop loss % dal prezzo (es. 2.5 → 2.5%)
        // Volume calcolato in modo che se SL colpito → perdita = TradeSizePct% del saldo
        // Formula: riskEUR × convRate / (ask × slPct/100)
        private double CalculateVolume(Symbol sym, double ask, double slPct)
        {
            double riskEur  = Account.Balance * (TradeSizePct / 100.0);
            string quoteCcy = sym.QuoteAsset.Name; // "USD", "EUR", "GBX", "GBP"

            Print($"[SMB DEBUG] {sym.Name} | Balance={Account.Balance:F0} {Account.Asset.Name} | Risk={riskEur:F0} EUR | Ask={ask} | SlPct={slPct:F2}% | QuoteCcy={quoteCcy}");

            double convRate = 1.0; // EUR → quote currency

            if (quoteCcy == "EUR")
            {
                convRate = 1.0;
            }
            else if (quoteCcy == "GBX")
            {
                // UK stocks in pence: 1 EUR = EURGBP × 100 pence
                var eurgbp = Symbols.GetSymbol("EURGBP");
                convRate = (eurgbp != null && eurgbp.Ask > 0) ? eurgbp.Ask * 100.0 : 100.0;
            }
            else if (quoteCcy == "GBP")
            {
                // FPMarkets: UK stocks in GBP/unit
                var eurgbp = Symbols.GetSymbol("EURGBP");
                convRate = (eurgbp != null && eurgbp.Ask > 0) ? eurgbp.Ask : 0.85;
            }
            else
            {
                // USD, CHF, ecc. — cerca EURUSD, EURCHF, ecc.
                var convSym = Symbols.GetSymbol("EUR" + quoteCcy);
                if (convSym != null && convSym.Ask > 0)
                    convRate = convSym.Ask;
                else
                {
                    // Prova inverso: USDEUR non esiste, usa 1/EURUSD
                    var revSym = Symbols.GetSymbol(quoteCcy + "EUR");
                    convRate = (revSym != null && revSym.Bid > 0) ? 1.0 / revSym.Bid : 1.0;
                }
            }

            // Perdita per unità se SL colpito = ask * slPct/100 (in quote currency)
            // Unità necessarie = riskEUR_in_quoteCcy / perdita_per_unita
            double slDistQuote = ask * (slPct / 100.0);
            double volumeUnits = (riskEur * convRate) / slDistQuote;

            Print($"[SMB DEBUG] convRate={convRate:F4} | slDistQuote={slDistQuote:F4} | rawUnits={volumeUnits:F2}");
            return sym.NormalizeVolumeInUnits(volumeUnits, RoundingMode.Down);
        }

        // -----------------------------------------------------------------------
        private int CountOpenPositions()
        {
            int n = 0;
            foreach (var pos in Positions)
                if (pos.Label != null && pos.Label.StartsWith(LABEL_PREFIX))
                    n++;
            return n;
        }

        private bool IsAlreadyOpen(string yfSymbol)
        {
            string label = LABEL_PREFIX + yfSymbol;
            foreach (var pos in Positions)
                if (pos.Label == label) return true;
            return false;
        }

        // Conta quanti segnali della settimana corrente sono già stati aperti
        private int CountWeekSignalsOpened(SignalFile signals)
        {
            int n = 0;
            foreach (var signal in signals.Signals)
                if (IsAlreadyOpen(signal.YfSymbol)) n++;
            return n;
        }

        // -----------------------------------------------------------------------
        // Scrive C:\TradeBridge\StockBot\portfolio_status.json
        // Il Python portfolio_updater.py legge questo file ogni ora e aggiorna Portfolio Status.md
        private void WritePortfolioStatus()
        {
            try
            {
                string portfolioPath = System.IO.Path.Combine(
                    System.IO.Path.GetDirectoryName(BridgePath) ?? @"C:\TradeBridge\StockBot",
                    "portfolio_status.json");

                // TUTTE le posizioni aperte sul conto demo (bot + manuali)
                var posLines = new System.Text.StringBuilder();
                posLines.Append("[");
                bool firstPos = true;
                double unrealizedTotal = 0;
                foreach (var pos in Positions)
                {
                    try
                    {
                        string displayName = (!string.IsNullOrEmpty(pos.Label) && pos.Label.StartsWith(LABEL_PREFIX))
                            ? pos.Label.Substring(LABEL_PREFIX.Length)
                            : (!string.IsNullOrEmpty(pos.Label) ? pos.Label : pos.SymbolName);
                        double pnl    = pos.NetProfit;
                        double pnlPct = Account.Balance > 0 ? pnl / Account.Balance * 100.0 : 0;
                        string sl     = pos.StopLoss.HasValue  ? pos.StopLoss.Value.ToString("F4", System.Globalization.CultureInfo.InvariantCulture)  : "null";
                        string tp     = pos.TakeProfit.HasValue ? pos.TakeProfit.Value.ToString("F4", System.Globalization.CultureInfo.InvariantCulture) : "null";
                        // CurrentPrice può fallire per simboli non sottoscritti — fallback su EntryPrice
                        double currentPrice;
                        try { currentPrice = pos.CurrentPrice; }
                        catch { currentPrice = pos.EntryPrice; }

                        unrealizedTotal += pnl;
                        if (!firstPos) posLines.Append(",");
                        firstPos = false;
                        posLines.Append("{");
                        posLines.Append($"\"yf_symbol\":\"{displayName}\",");
                        posLines.Append($"\"ct_symbol\":\"{pos.SymbolName}\",");
                        posLines.Append($"\"direction\":\"{pos.TradeType}\",");
                        posLines.Append($"\"volume\":{pos.VolumeInUnits.ToString(System.Globalization.CultureInfo.InvariantCulture)},");
                        posLines.Append($"\"entry_price\":{pos.EntryPrice.ToString("F4", System.Globalization.CultureInfo.InvariantCulture)},");
                        posLines.Append($"\"current_price\":{currentPrice.ToString("F4", System.Globalization.CultureInfo.InvariantCulture)},");
                        posLines.Append($"\"sl\":{sl},");
                        posLines.Append($"\"tp\":{tp},");
                        posLines.Append($"\"unrealized_pnl\":{pnl.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)},");
                        posLines.Append($"\"unrealized_pnl_pct\":{pnlPct.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)},");
                        posLines.Append($"\"opened_at\":\"{pos.EntryTime:yyyy-MM-ddTHH:mm:ssZ}\"");
                        posLines.Append("}");
                    }
                    catch (Exception posEx)
                    {
                        Print($"[SMB] Portfolio: skip {pos.SymbolName} — {posEx.Message}");
                    }
                }
                posLines.Append("]");

                // TUTTO lo storico chiuso del conto demo (bot + manuali)
                var histLines = new System.Text.StringBuilder();
                histLines.Append("[");
                bool firstHist = true;
                double realizedTotal = 0;
                int totalClosed = 0, wins = 0;
                foreach (var trade in History)
                {
                    if (trade.EntryTime < HISTORY_START_UTC) continue;
                    totalClosed++;
                    realizedTotal += trade.NetProfit;
                    if (trade.NetProfit > 0) wins++;
                    if (!firstHist) histLines.Append(",");
                    firstHist = false;
                    string displayName = (!string.IsNullOrEmpty(trade.Label) && trade.Label.StartsWith(LABEL_PREFIX))
                        ? trade.Label.Substring(LABEL_PREFIX.Length)
                        : (!string.IsNullOrEmpty(trade.Label) ? trade.Label : trade.SymbolName);
                    histLines.Append("{");
                    histLines.Append($"\"yf_symbol\":\"{displayName}\",");
                    histLines.Append($"\"ct_symbol\":\"{trade.SymbolName}\",");
                    histLines.Append($"\"direction\":\"{trade.TradeType}\",");
                    histLines.Append($"\"volume\":{trade.VolumeInUnits.ToString(System.Globalization.CultureInfo.InvariantCulture)},");
                    histLines.Append($"\"entry_price\":{trade.EntryPrice.ToString("F4", System.Globalization.CultureInfo.InvariantCulture)},");
                    histLines.Append($"\"close_price\":{trade.ClosingPrice.ToString("F4", System.Globalization.CultureInfo.InvariantCulture)},");
                    histLines.Append($"\"net_pnl\":{trade.NetProfit.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)},");
                    histLines.Append($"\"opened_at\":\"{trade.EntryTime:yyyy-MM-ddTHH:mm:ssZ}\",");
                    histLines.Append($"\"closed_at\":\"{trade.ClosingTime:yyyy-MM-ddTHH:mm:ssZ}\"");
                    histLines.Append("}");
                }
                histLines.Append("]");

                double equity = Account.Balance + unrealizedTotal;
                var json = new System.Text.StringBuilder();
                json.Append("{");
                json.Append($"\"updated_at\":\"{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\",");
                json.Append($"\"balance\":{Account.Balance.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)},");
                json.Append($"\"equity\":{equity.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)},");
                json.Append($"\"unrealized_pnl\":{unrealizedTotal.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)},");
                json.Append($"\"realized_pnl\":{realizedTotal.ToString("F2", System.Globalization.CultureInfo.InvariantCulture)},");
                json.Append($"\"total_closed\":{totalClosed},");
                json.Append($"\"wins\":{wins},");
                json.Append($"\"positions\":{posLines},");
                json.Append($"\"closed_trades\":{histLines}");
                json.Append("}");

                System.IO.File.WriteAllText(portfolioPath, json.ToString());
            }
            catch (Exception ex)
            {
                Print($"[SMB] Errore scrittura portfolio JSON: {ex.Message}");
            }
        }

        // -----------------------------------------------------------------------
        protected override void OnStop()
        {
            WritePortfolioStatus();
            Print("[SMB] StockMarketBot fermato.");
        }
    }

    // -----------------------------------------------------------------------
    // Modelli JSON
    // -----------------------------------------------------------------------

    public class SignalFile
    {
        [JsonPropertyName("generated_at")]
        public string GeneratedAt { get; set; }

        [JsonPropertyName("week")]
        public string Week { get; set; }

        [JsonPropertyName("signals")]
        public List<SignalData> Signals { get; set; }
    }

    public class SignalData
    {
        [JsonPropertyName("yf_symbol")]
        public string YfSymbol { get; set; }

        [JsonPropertyName("ct_symbol")]
        public string CtSymbol { get; set; }

        [JsonPropertyName("sl_pct")]
        public double SlPct { get; set; }

        [JsonPropertyName("tp_pct")]
        public double TpPct { get; set; }

        [JsonPropertyName("score")]
        public double Score { get; set; }
    }
}
