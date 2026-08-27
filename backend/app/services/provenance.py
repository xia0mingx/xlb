"""Where an ingredient comes from: natural, nature-identical, or synthetic.

Deliberately kept out of `ingredients.json`. That file is the ingredient
dictionary and grows as new products are ingested; provenance is a separate
judgement about each entry, and holding it here means the dictionary can be
extended without touching this, and this can be corrected without touching the
dictionary.

**Provenance is not a safety or quality signal, and nothing in the recommender
scores on it.** Squalane from olives and squalane from sugarcane fermentation are
the same molecule with the same effect on skin. Meanwhile the most common
contact allergens in this dictionary - limonene, linalool, essential oils - are
natural, and two of the gentlest occlusives are synthetic. The field exists
because people want to know, and because some avoid animal- or petroleum-derived
material for reasons of their own. It is presented as origin, not virtue.

The three buckets:

`natural`
    Derived from a plant, mineral or animal source, processed only enough to be
    usable, and still recognisably that material: extracts, cold-pressed oils,
    butters, ferments, mined minerals.

`nature_identical`
    A single molecule that also occurs in nature, but manufactured - by
    fermentation or synthesis - rather than extracted. Chemically
    indistinguishable from the natural article, and usually purer. Most of the
    well-studied actives live here.

`synthetic`
    Made by chemical synthesis with no natural counterpart, or so thoroughly
    transformed from its feedstock that the origin no longer describes it.
    Silicones, most UV filters, most preservatives, refined petrolatum.

`None`
    We do not know, and say so. `Fragrance` is the honest example: an
    undisclosed mixture that may be either.
"""

from __future__ import annotations

import re

from app.services.text import normalize_text

NATURAL = "natural"
NATURE_IDENTICAL = "nature_identical"
SYNTHETIC = "synthetic"

LABELS: dict[str, str] = {
    NATURAL: "Natural",
    NATURE_IDENTICAL: "Nature-identical",
    SYNTHETIC: "Synthetic",
}

DESCRIPTIONS: dict[str, str] = {
    NATURAL: "From a plant, mineral or animal source, still recognisably that material.",
    NATURE_IDENTICAL: "The same molecule found in nature, but manufactured rather than extracted.",
    SYNTHETIC: "Made by chemical synthesis, with no natural counterpart.",
}

# --- explicit classifications ----------------------------------------------

_NATURAL = {
    # Botanical extracts, oils and butters
    "Arachis Hypogaea Oil", "Argania Spinosa Kernel Oil", "Avena Sativa Kernel Extract",
    "Butyrospermum Parkii Butter", "Camellia Sinensis Leaf Extract", "Centella Asiatica Extract",
    "Cocos Nucifera Oil", "Corylus Avellana Seed Oil", "Citrus Limon Peel Oil",
    "Eucalyptus Globulus Leaf Oil", "Evernia Furfuracea Extract", "Evernia Prunastri Extract",
    "Glycine Soja Oil", "Glycyrrhiza Glabra Root Extract", "Helianthus Annuus Seed Oil",
    "Lavandula Angustifolia Oil", "Melaleuca Alternifolia Leaf Oil", "Mentha Piperita Oil",
    "Myroxylon Pereirae Resin", "Olea Europaea Fruit Oil", "Oryza Sativa Extract",
    "Panax Ginseng Root Extract", "Prunus Amygdalus Dulcis Oil", "Rosa Canina Fruit Oil",
    "Sesamum Indicum Seed Oil", "Simmondsia Chinensis Seed Oil", "Triticum Vulgare Germ Oil",
    "Vitis Vinifera Seed Oil", "Willow Bark Extract", "Rice Bran Extract", "Colloidal Oatmeal",
    "Colophonium",
    # Bee and animal derived
    "Honey Extract", "Propolis Extract", "Snail Secretion Filtrate", "Lanolin", "Lanolin Alcohol",
    # Ferments
    "Bifida Ferment Lysate", "Galactomyces Ferment Filtrate", "Lactobacillus Ferment",
    "Saccharomyces Ferment Filtrate",
    # Protein hydrolysates - processed, but from a named natural protein
    "Hydrolyzed Collagen", "Hydrolyzed Wheat Protein",
    # Mined minerals
    "Titanium Dioxide", "Zinc Oxide",
    # Water
    "Water", "Aqua",
}

_NATURE_IDENTICAL = {
    # Humectants and barrier material
    "Glycerin", "Squalane", "Hyaluronic Acid", "Sodium Hyaluronate",
    "Hydrolyzed Hyaluronic Acid", "Sodium Acetylated Hyaluronate", "Betaine", "Urea",
    "Trehalose", "Sodium PCA", "Beta-Glucan", "Panthenol", "Allantoin", "Allantoin Panthenol",
    "Cholesterol", "Ceramide AP", "Ceramide EOP", "Ceramide NP", "Ceramide NS",
    "Phytosphingosine",
    # Antioxidants and actives
    "Niacinamide", "Caffeine", "Tocopherol", "Ascorbic Acid", "Ferulic Acid", "Resveratrol",
    "Astaxanthin", "Coenzyme Q10", "Ubiquinone", "Glutathione", "Adenosine", "Bakuchiol",
    "Retinol", "Retinal", "Sulfur", "Azelaic Acid", "Kojic Acid", "Arbutin", "Alpha-Arbutin",
    # Acids
    "Lactic Acid", "Glycolic Acid", "Malic Acid", "Tartaric Acid", "Mandelic Acid",
    "Citric Acid", "Salicylic Acid", "Gluconolactone", "Lactobionic Acid",
    # Centella constituents
    "Asiatic Acid", "Asiaticoside", "Madecassic Acid", "Madecassoside",
    # Soothing / sensory
    "Bisabolol", "Menthol", "Camphor",
    # Fatty alcohols and acids
    "Stearic Acid", "Cetyl Alcohol", "Cetearyl Alcohol",
    # Gums and mild preservatives
    "Xanthan Gum", "Potassium Sorbate", "Sodium Benzoate", "Benzyl Alcohol",
    "Ethanol", "Zinc PCA",
    # Fragrance allergens that occur as natural essential-oil constituents,
    # even though the material used is usually manufactured.
    "Limonene", "Linalool", "Geraniol", "Citral", "Citronellol", "Eugenol", "Isoeugenol",
    "Coumarin", "Farnesol", "Cinnamal", "Cinnamyl Alcohol", "Anise Alcohol",
    "Benzyl Benzoate", "Benzyl Cinnamate", "Benzyl Salicylate", "Amyl Cinnamal",
    "Amylcinnamyl Alcohol", "Hexyl Cinnamal",
}

_SYNTHETIC = {
    # Silicones
    "Dimethicone", "Dimethicone Crosspolymer", "Cyclopentasiloxane",
    # Preservatives and boosters
    "Phenoxyethanol", "Methylparaben", "Propylparaben", "Chlorphenesin",
    "Methylisothiazolinone", "Methylchloroisothiazolinone", "DMDM Hydantoin",
    "Diazolidinyl Urea", "Imidazolidinyl Urea", "Quaternium-15", "Ethylhexylglycerin",
    "1,2-Hexanediol",
    # Glycols and solvents
    "Butylene Glycol", "1,3-Butylene Glycol", "Propylene Glycol", "Dipropylene Glycol",
    "Pentylene Glycol", "Propanediol", "Alcohol Denat.",
    # Chelators, thickeners, film formers
    "Disodium EDTA", "Tetrasodium EDTA", "Carbomer", "Sodium Polyacrylate",
    "Ethylene/Propylene/Styrene Copolymer",
    # Surfactants and emulsifiers
    "Sodium Lauryl Sulfate", "Sodium Laureth Sulfate", "Cocamidopropyl Betaine",
    "Coco-Glucoside", "Decyl Glucoside", "Sodium Cocoyl Isethionate",
    "Potassium Cocoyl Glycinate", "Isoceteth-20", "Polysorbate 20", "Glyceryl Stearate",
    # Emollient esters
    "Caprylic/Capric Triglyceride", "Isodecyl Neopentanoate", "Isononyl Isononanoate",
    "Isopropyl Myristate", "Isopropyl Palmitate",
    # Organic UV filters
    "Avobenzone", "Benzophenone-3", "Homosalate", "Octinoxate", "Octocrylene",
    "Ethylhexyl Triazone", "Tinosorb S", "Uvinul A Plus",
    # Vitamin C derivatives - stabilised forms with no natural counterpart
    "3-O-Ethyl Ascorbic Acid", "Ascorbyl Glucoside", "Ascorbyl Tetraisopalmitate",
    "Magnesium Ascorbyl Phosphate", "Sodium Ascorbyl Phosphate", "Tetrahexyldecyl Ascorbate",
    # Esterified vitamin derivatives - stabilised forms, made by esterifying the
    # natural molecule, so classed with the other esters rather than with the
    # vitamin they derive from.
    "Adapalene", "Hydroxypinacolone Retinoate", "Retinyl Palmitate", "Retinyl Retinoate",
    "Tocopheryl Acetate",
    # Peptides
    "Acetyl Hexapeptide-8", "Copper Tripeptide-1", "Palmitoyl Tetrapeptide-7",
    "Palmitoyl Tripeptide-1",
    # Salicylate derivatives and other actives
    "Benzoyl Peroxide", "Betaine Salicylate", "Capryloyl Salicylic Acid", "Tranexamic Acid",
    # pH adjusters
    "Sodium Hydroxide",
    # Petroleum derived - the feedstock is geological, but refining leaves
    # nothing of the original material's identity.
    "Petrolatum", "Mineral Oil",
    # Synthetic fragrance molecules
    "Butylphenyl Methylpropional", "Methyl 2-Octynoate", "Hydroxycitronellal",
    "Hydroxyisohexyl 3-Cyclohexene Carboxaldehyde", "Alpha-Isomethyl Ionone",
}

# Undisclosed mixtures. Named explicitly so the botanical fallback below cannot
# guess at them.
_UNKNOWN = {"Fragrance", "Parfum"}


_NATURAL_KEYS = {normalize_text(n) for n in _NATURAL}
_NATURE_IDENTICAL_KEYS = {normalize_text(n) for n in _NATURE_IDENTICAL}
_SYNTHETIC_KEYS = {normalize_text(n) for n in _SYNTHETIC}
_UNKNOWN_KEYS = {normalize_text(n) for n in _UNKNOWN}

# Fallback for ingredients added to the dictionary after this table was written.
# A botanical INCI name is a Latin binomial followed by the plant part and the
# preparation - "Camellia Sinensis Leaf Extract" - which is a reliable enough
# shape to call natural. Everything else stays unknown rather than guessed.
_BOTANICAL_RE = re.compile(
    r"^[a-z]+ [a-z]+ .*\b(extract|oil|butter|juice|water|powder|wax|resin|"
    r"filtrate|lysate|ferment|flower|leaf|root|seed|fruit|bark|kernel|peel)\b"
)
_PREPARATION_RE = re.compile(r"\b(ferment filtrate|ferment lysate|flower water|floral water)\b")


def classify(inci_name: str) -> str | None:
    """Provenance for one INCI name, or None when we genuinely do not know."""
    if not inci_name:
        return None

    key = normalize_text(inci_name)

    if key in _UNKNOWN_KEYS:
        return None
    if key in _NATURAL_KEYS:
        return NATURAL
    if key in _NATURE_IDENTICAL_KEYS:
        return NATURE_IDENTICAL
    if key in _SYNTHETIC_KEYS:
        return SYNTHETIC

    if _BOTANICAL_RE.match(key) or _PREPARATION_RE.search(key):
        return NATURAL

    return None


def summarise(sources: list[str | None]) -> dict[str, int]:
    """Count each bucket across an ingredient list.

    `unknown` is reported rather than folded into another bucket, because a
    product whose provenance we mostly cannot determine should not look like a
    product that is mostly synthetic.
    """
    counts = {NATURAL: 0, NATURE_IDENTICAL: 0, SYNTHETIC: 0, "unknown": 0}
    for source in sources:
        counts[source if source in counts else "unknown"] += 1
    return counts
