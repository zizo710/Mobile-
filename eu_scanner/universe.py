"""European tradable universe.

Tickers use Yahoo Finance suffixes:
  .L  = London Stock Exchange
  .DE = Xetra (Germany)
  .PA = Euronext Paris
  .AS = Euronext Amsterdam
  .MI = Borsa Italiana (Milan)
  .MC = Bolsa de Madrid
  .SW = SIX Swiss Exchange
  .BR = Euronext Brussels
  .HE = Helsinki
  .ST = Stockholm
  .CO = Copenhagen
  .OL = Oslo
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Underlying:
    ticker: str
    name: str
    sector: str
    country: str


# Indices and broad benchmarks (used for context, not ranked)
INDICES = [
    Underlying("^STOXX50E", "Euro Stoxx 50", "Index", "EU"),
    Underlying("^STOXX", "Stoxx Europe 600", "Index", "EU"),
    Underlying("^FTSE", "FTSE 100", "Index", "UK"),
    Underlying("^GDAXI", "DAX 40", "Index", "DE"),
    Underlying("^FCHI", "CAC 40", "Index", "FR"),
    Underlying("^IBEX", "IBEX 35", "Index", "ES"),
    Underlying("FTSEMIB.MI", "FTSE MIB", "Index", "IT"),
    Underlying("^AEX", "AEX", "Index", "NL"),
    Underlying("^SSMI", "SMI", "Index", "CH"),
]


# Single names — large-cap, liquid, and typically in single-stock futures / options.
SINGLE_NAMES = [
    # ===== UK =====
    Underlying("SHEL.L", "Shell", "Energy", "UK"),
    Underlying("BP.L", "BP", "Energy", "UK"),
    Underlying("AZN.L", "AstraZeneca", "Healthcare", "UK"),
    Underlying("GSK.L", "GSK", "Healthcare", "UK"),
    Underlying("ULVR.L", "Unilever", "Staples", "UK"),
    Underlying("HSBA.L", "HSBC", "Financials", "UK"),
    Underlying("BARC.L", "Barclays", "Financials", "UK"),
    Underlying("LLOY.L", "Lloyds", "Financials", "UK"),
    Underlying("NWG.L", "NatWest", "Financials", "UK"),
    Underlying("STAN.L", "Standard Chartered", "Financials", "UK"),
    Underlying("RIO.L", "Rio Tinto", "Materials", "UK"),
    Underlying("GLEN.L", "Glencore", "Materials", "UK"),
    Underlying("AAL.L", "Anglo American", "Materials", "UK"),
    Underlying("BATS.L", "British American Tobacco", "Staples", "UK"),
    Underlying("DGE.L", "Diageo", "Staples", "UK"),
    Underlying("REL.L", "RELX", "Comm Svcs", "UK"),
    Underlying("VOD.L", "Vodafone", "Comm Svcs", "UK"),
    Underlying("TSCO.L", "Tesco", "Staples", "UK"),
    Underlying("NG.L", "National Grid", "Utilities", "UK"),
    Underlying("CRH.L", "CRH", "Materials", "UK"),
    # ===== Germany =====
    Underlying("SAP.DE", "SAP", "Technology", "DE"),
    Underlying("SIE.DE", "Siemens", "Industrials", "DE"),
    Underlying("ALV.DE", "Allianz", "Financials", "DE"),
    Underlying("DBK.DE", "Deutsche Bank", "Financials", "DE"),
    Underlying("DTE.DE", "Deutsche Telekom", "Comm Svcs", "DE"),
    Underlying("BAS.DE", "BASF", "Materials", "DE"),
    Underlying("BAYN.DE", "Bayer", "Healthcare", "DE"),
    Underlying("BMW.DE", "BMW", "Discretionary", "DE"),
    Underlying("MBG.DE", "Mercedes-Benz", "Discretionary", "DE"),
    Underlying("VOW3.DE", "Volkswagen", "Discretionary", "DE"),
    Underlying("P911.DE", "Porsche AG", "Discretionary", "DE"),
    Underlying("ADS.DE", "Adidas", "Discretionary", "DE"),
    Underlying("MUV2.DE", "Munich Re", "Financials", "DE"),
    Underlying("IFX.DE", "Infineon", "Technology", "DE"),
    Underlying("RHM.DE", "Rheinmetall", "Industrials", "DE"),
    Underlying("AIR.DE", "Airbus", "Industrials", "DE"),
    Underlying("DHL.DE", "DHL Group", "Industrials", "DE"),
    Underlying("HEN3.DE", "Henkel", "Staples", "DE"),
    Underlying("MRK.DE", "Merck KGaA", "Healthcare", "DE"),
    Underlying("CON.DE", "Continental", "Discretionary", "DE"),
    # ===== France =====
    Underlying("MC.PA", "LVMH", "Discretionary", "FR"),
    Underlying("OR.PA", "L'Oreal", "Staples", "FR"),
    Underlying("RMS.PA", "Hermes", "Discretionary", "FR"),
    Underlying("CDI.PA", "Christian Dior", "Discretionary", "FR"),
    Underlying("SAN.PA", "Sanofi", "Healthcare", "FR"),
    Underlying("TTE.PA", "TotalEnergies", "Energy", "FR"),
    Underlying("BNP.PA", "BNP Paribas", "Financials", "FR"),
    Underlying("ACA.PA", "Credit Agricole", "Financials", "FR"),
    Underlying("GLE.PA", "Societe Generale", "Financials", "FR"),
    Underlying("CS.PA", "AXA", "Financials", "FR"),
    Underlying("AI.PA", "Air Liquide", "Materials", "FR"),
    Underlying("SU.PA", "Schneider Electric", "Industrials", "FR"),
    Underlying("SAF.PA", "Safran", "Industrials", "FR"),
    Underlying("CAP.PA", "Capgemini", "Technology", "FR"),
    Underlying("DG.PA", "Vinci", "Industrials", "FR"),
    Underlying("KER.PA", "Kering", "Discretionary", "FR"),
    Underlying("EL.PA", "EssilorLuxottica", "Healthcare", "FR"),
    Underlying("BN.PA", "Danone", "Staples", "FR"),
    Underlying("ENGI.PA", "Engie", "Utilities", "FR"),
    Underlying("STLAP.PA", "Stellantis", "Discretionary", "FR"),
    # ===== Netherlands =====
    Underlying("ASML.AS", "ASML", "Technology", "NL"),
    Underlying("PRX.AS", "Prosus", "Discretionary", "NL"),
    Underlying("INGA.AS", "ING Groep", "Financials", "NL"),
    Underlying("ADYEN.AS", "Adyen", "Technology", "NL"),
    Underlying("HEIA.AS", "Heineken", "Staples", "NL"),
    Underlying("AD.AS", "Ahold Delhaize", "Staples", "NL"),
    Underlying("PHIA.AS", "Philips", "Healthcare", "NL"),
    Underlying("REN.AS", "Relx NV", "Comm Svcs", "NL"),
    Underlying("WKL.AS", "Wolters Kluwer", "Industrials", "NL"),
    Underlying("ASM.AS", "ASM International", "Technology", "NL"),
    # ===== Switzerland =====
    Underlying("NESN.SW", "Nestle", "Staples", "CH"),
    Underlying("ROG.SW", "Roche", "Healthcare", "CH"),
    Underlying("NOVN.SW", "Novartis", "Healthcare", "CH"),
    Underlying("UBSG.SW", "UBS", "Financials", "CH"),
    Underlying("ZURN.SW", "Zurich Insurance", "Financials", "CH"),
    Underlying("ABBN.SW", "ABB", "Industrials", "CH"),
    Underlying("CFR.SW", "Richemont", "Discretionary", "CH"),
    Underlying("LONN.SW", "Lonza", "Healthcare", "CH"),
    Underlying("HOLN.SW", "Holcim", "Materials", "CH"),
    Underlying("SREN.SW", "Swiss Re", "Financials", "CH"),
    # ===== Italy =====
    Underlying("ENI.MI", "Eni", "Energy", "IT"),
    Underlying("ENEL.MI", "Enel", "Utilities", "IT"),
    Underlying("ISP.MI", "Intesa Sanpaolo", "Financials", "IT"),
    Underlying("UCG.MI", "UniCredit", "Financials", "IT"),
    Underlying("STLAM.MI", "Stellantis Milan", "Discretionary", "IT"),
    Underlying("RACE.MI", "Ferrari", "Discretionary", "IT"),
    Underlying("G.MI", "Generali", "Financials", "IT"),
    Underlying("STMMI.MI", "STMicroelectronics", "Technology", "IT"),
    Underlying("MONC.MI", "Moncler", "Discretionary", "IT"),
    Underlying("PRY.MI", "Prysmian", "Industrials", "IT"),
    # ===== Spain =====
    Underlying("SAN.MC", "Banco Santander", "Financials", "ES"),
    Underlying("BBVA.MC", "BBVA", "Financials", "ES"),
    Underlying("IBE.MC", "Iberdrola", "Utilities", "ES"),
    Underlying("ITX.MC", "Inditex", "Discretionary", "ES"),
    Underlying("REP.MC", "Repsol", "Energy", "ES"),
    Underlying("TEF.MC", "Telefonica", "Comm Svcs", "ES"),
    Underlying("FER.MC", "Ferrovial", "Industrials", "ES"),
    Underlying("AENA.MC", "Aena", "Industrials", "ES"),
    # ===== Nordics / Other =====
    Underlying("NOVO-B.CO", "Novo Nordisk", "Healthcare", "DK"),
    Underlying("MAERSK-B.CO", "AP Moller Maersk", "Industrials", "DK"),
    Underlying("VWS.CO", "Vestas Wind", "Industrials", "DK"),
    Underlying("ATCO-A.ST", "Atlas Copco", "Industrials", "SE"),
    Underlying("VOLV-B.ST", "Volvo", "Industrials", "SE"),
    Underlying("INVE-B.ST", "Investor", "Financials", "SE"),
    Underlying("EQNR.OL", "Equinor", "Energy", "NO"),
    Underlying("NOKIA.HE", "Nokia", "Technology", "FI"),
    Underlying("ABI.BR", "AB InBev", "Staples", "BE"),
    Underlying("KBC.BR", "KBC Group", "Financials", "BE"),
]


def all_single_names() -> list[Underlying]:
    return list(SINGLE_NAMES)


def all_indices() -> list[Underlying]:
    return list(INDICES)
