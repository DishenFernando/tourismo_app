"""Five source-referenced ENGLISH pilot guides for editorial review.

No schedule, pricing, photo license or unsourced exact attraction coordinates
are asserted here. These records remain `sample` until a human admin approves.
References collected November 2026; link visibility is NOT a licensing grant.
"""

# Each guide's main source is a primary heritage/municipal authority.
SOURCES = {
    'kandy_heritage': ('UNESCO World Heritage Centre — Sacred City of Kandy', 'https://whc.unesco.org/en/list/450/'),
    'galle_heritage': ('UNESCO World Heritage Centre — Old Town of Galle', 'https://whc.unesco.org/en/list/451/'),
    'anuradhapura_heritage': ('UNESCO World Heritage Centre — Sacred City of Anuradhapura', 'https://whc.unesco.org/en/list/200/'),
    'sigiriya_heritage': ('UNESCO World Heritage Centre — Ancient City of Sigiriya', 'https://whc.unesco.org/en/list/202/'),
    'sigiriya_ccf': ('Central Cultural Fund — Sigiriya Rock Fortress', 'https://ccf.gov.lk/heritage-sites/sigiriya-rock-fortress/'),
    'nuwara_municipal': ('Nuwara Eliya Municipal Council — Town Attractions', 'https://www.nuwaraeliya.mc.gov.lk/index.php/information/about'),
    'peradeniya_gardens': ('Department of National Botanic Gardens — Peradeniya', 'https://en.botanicgardens.gov.lk/service/royal-botanic-gardens-peradeniya/'),
    'hakgala_gardens': ('Department of National Botanic Gardens — Hakgala', 'https://botanicgardens.gov.lk/service/botanic-gardens-hakgala/'),
    'anuradhapura_archaeology': ('Department of Archaeology — Anuradhapura Local Sites', 'https://archaeology.gov.lk/index.php/anucircuit'),
}

# Keys are destination slugs; original_overview is the exact Phase 2.1/2.3 seed.
# Only unchanged samples will be enriched. Published content and pending revisions are safe.
GUIDES = {
    'kandy': {
        'source': 'kandy_heritage',
        'original_overview': "Kandy is a UNESCO World Heritage sacred city and the location of the Temple of the Tooth Relic.",
        'overview': (
            'Kandy is a cultural and religious centre in Sri Lanka’s central hills. UNESCO recognises the Sacred City of Kandy, the last capital of the Sinhala kings, for its heritage and association with the Temple of the Tooth Relic. Visitors can build a heritage-focused trip around the sacred city and add a separate garden excursion to Peradeniya, just outside central Kandy. The city remains an active place of worship, not only a sightseeing setting.'
        ),
        'highlights': [
            'UNESCO World Heritage sacred city and Kandyan royal history',
            'Temple of the Tooth Relic and continuing pilgrimage traditions',
            'Botanical collections at nearby Peradeniya Gardens',
            'A mix of historical landmarks and modern urban life',
        ],
        'local_tips': [
            'Dress respectfully when visiting religious spaces, and follow instructions on site.',
            'Plan time for both the sacred city and a separate visit to the gardens; they are different locations.',
            'Check current temple ceremonies, access restrictions and visitor rules directly with the site.',
            'Budget independently for transport and entry: Tourismo does not display unverified prices.',
        ],
    },
    'galle': {
        'source': 'galle_heritage',
        'original_overview': 'Galle Fort is a UNESCO World Heritage historic town with fortifications reflecting South Asian and European architectural traditions.',
        'overview': (
            'Galle’s historic fortified town occupies a coastal promontory in southern Sri Lanka. UNESCO describes an urban landscape shaped by Portuguese origins, Dutch-period fortifications and the meeting of European planning with South Asian building traditions. The ramparts, historic street pattern and lived-in neighbourhoods reward slow exploration. Remember that the old town is also a residential and working community, and that coastal conditions can change quickly.'
        ),
        'highlights': [
            'UNESCO-listed Old Town of Galle and its Fortifications',
            'Fortification walls and bastions shaped by the rocky coast',
            'Historic street layout, shaded verandas and courtyard architecture',
            'Coastal views alongside an active local community',
        ],
        'local_tips': [
            'Walk thoughtfully in residential streets and respect private properties.',
            'Take care on exposed fortifications and coastal edges, especially in rain or strong winds.',
            'Preserve the historic fabric: do not climb restricted walls or damage monuments.',
            'Confirm opening arrangements for individual museums, churches and businesses separately.',
        ],
    },
    'anuradhapura': {
        'source': 'anuradhapura_heritage',
        'original_overview': "Anuradhapura is a UNESCO World Heritage site associated with Sri Lanka's early Buddhist history and former royal capital.",
        'overview': (
            'Anuradhapura is an extensive sacred and archaeological landscape in Sri Lanka’s North Central Province. The UNESCO-listed city developed around a cutting from the Bodhi tree tradition and flourished as a major political and Buddhist centre for many centuries. Its temples, stupas and monastic remains are spread across multiple areas rather than confined to a single compact attraction. A visit benefits from realistic travel time between sites and sensitivity to ongoing worship.'
        ),
        'highlights': [
            'UNESCO World Heritage sacred city and ancient capital',
            'Sri Maha Bodhi tradition associated with the sacred fig tree',
            'Large historic monastery and stupa landscape',
            'Religious pilgrimage traditions that remain active today',
        ],
        'local_tips': [
            'Allow extra time between the scattered monuments; one map point is not the whole site.',
            'Follow dress codes and footwear instructions at places of worship.',
            'Carry drinking water and take breaks during exposed daytime visits.',
            'Check current entry arrangements and heritage-area restrictions with official custodians.',
        ],
    },
    'sigiriya': {
        'source': 'sigiriya_heritage',
        'original_overview': 'The Ancient City of Sigiriya is a UNESCO World Heritage archaeological site in Sri Lanka, celebrated for its historic rock citadel and cultural landscape. The point on this guide is a UNESCO site reference, not an entrance.',
        'overview': (
            'Sigiriya, in Sri Lanka’s Cultural Triangle, is a UNESCO World Heritage archaeological site built around a striking rock plateau. Its surviving landscape combines a royal citadel with historic gardens, defensive features, paintings and architectural remains. The Central Cultural Fund documents the water gardens, frescoes, mirror wall and lion-paw gateway as distinct parts of the visitor experience. The UNESCO location marker is a property reference, not a verified entrance or walking route.'
        ),
        'highlights': [
            'UNESCO-listed ancient city and fifth-century rock citadel',
            'Historic water gardens and engineered landscape',
            'Frescoes and the ancient Mirror Wall',
            'Lion-paw gateway and ruins on the rock plateau',
        ],
        'local_tips': [
            'The ascent involves many steps and exposed sections; assess personal mobility and weather.',
            'Do not touch paintings or historic surfaces, and follow photography restrictions.',
            'Check official admission, seasonal access and conservation notices before setting out.',
            'Use current on-site signs for entrances and routes: the UNESCO marker is not navigation guidance.',
        ],
    },
    'nuwara-eliya': {
        'source': 'nuwara_municipal',
        'original_overview': 'Nuwara Eliya is a hill-country city known for its cool climate, parks and Gregory Lake, a local recreational landmark.',
        'overview': (
            'Nuwara Eliya is a highland city recognised for its lakeside recreation, gardens and cooler hill-country surroundings. The Municipal Council highlights Gregory Lake and Victoria Park as attractions within the town. Hakgala Botanic Gardens lies outside the centre along the Badulla Road, according to the Department of National Botanic Gardens. Together they offer a mix of relaxed town walking and plant-focused excursions, but individual activity availability and weather must be checked close to travel.'
        ),
        'highlights': [
            'Gregory Lake and its recreation areas',
            'Victoria Park and its garden landscape',
            'Hakgala Botanic Gardens as an excursion outside the town centre',
            'Cooler hill-country setting and botanical interest',
        ],
        'local_tips': [
            'Pack for changing highland conditions, including rain and cooler evenings.',
            'Check boating and other lake activities locally; operations depend on conditions.',
            'Allow separate travel time to Hakgala, which is outside central Nuwara Eliya.',
            'Confirm current park/garden opening, access, and ticket arrangements with the operators.',
        ],
    },
}

# Each POI has its own official source; omitted coordinates are intentional.
# The original five general heritage/landmark POIs remain in the database.
POIS = (
    ('kandy', 'temple-of-the-tooth-relic', 'Temple of the Tooth Relic', 'heritage', 'kandy_heritage',
     'The Buddhist Temple of the Tooth Relic is a principal pilgrimage focus within the UNESCO-listed Sacred City of Kandy.',
     'Observe site-specific worship, dress and photography rules.'),
    ('kandy', 'peradeniya-royal-botanic-gardens', 'Royal Botanic Gardens, Peradeniya', 'nature', 'peradeniya_gardens',
     'A botanical garden west of Kandy known for its collections of orchids, palms, spice plants and other flora.',
     'This is outside central Kandy; check official access and allow travel time.'),
    ('galle', 'galle-fort-ramparts', 'Galle Fort Ramparts', 'heritage', 'galle_heritage',
     'The fortifications and bastions form a defining part of the UNESCO-listed old town, adapted to the rocky coastal setting.',
     'Observe barriers and avoid exposed edges during rough weather.'),
    ('galle', 'galle-fort-historic-streets', 'Galle Fort Historic Streets', 'culture', 'galle_heritage',
     'The fort’s historic street grid, verandas and courtyards illustrate the meeting of European planning and South Asian building traditions.',
     'Respect homes, religious buildings and private property in this lived-in town.'),
    ('anuradhapura', 'jaya-sri-maha-bodhi', 'Jaya Sri Maha Bodhi', 'heritage', 'anuradhapura_heritage',
     'The sacred Bodhi tree tradition lies at the heart of Anuradhapura’s UNESCO-recognised Buddhist history.',
     'Treat this as an active sacred place and follow instructions from custodians.'),
    ('anuradhapura', 'ruwanwelisaya', 'Ruwanwelisaya', 'heritage', 'anuradhapura_archaeology',
     'Ruwanwelisaya is among the notable sacred monuments listed by Sri Lanka’s Department of Archaeology near Anuradhapura.',
     'Site access and pilgrimage etiquette should be checked locally.'),
    ('sigiriya', 'sigiriya-water-gardens', 'Sigiriya Water Gardens', 'heritage', 'sigiriya_ccf',
     'Part of the historical Sigiriya landscape, with arranged pools, channels and features demonstrating water-management design.',
     'Stay on signed paths to protect archaeological remains.'),
    ('sigiriya', 'sigiriya-frescoes', 'Sigiriya Frescoes', 'heritage', 'sigiriya_ccf',
     'Surviving paintings on the rock form a significant part of the ancient city’s artistic heritage.',
     'Observe all official restrictions on photography and touching surfaces.'),
    ('sigiriya', 'sigiriya-lion-gateway', 'Sigiriya Lion Gateway', 'heritage', 'sigiriya_ccf',
     'The historic gateway is marked by surviving lion-paw structures along the ancient ascent.',
     'The ascent can be physically demanding; use approved routes and steps.'),
    ('nuwara-eliya', 'victoria-park-nuwara-eliya', 'Victoria Park', 'nature', 'nuwara_municipal',
     'A landscaped park in Nuwara Eliya identified by the Municipal Council as an attraction for walking and birdwatching.',
     'Check current public access before visiting.'),
    ('nuwara-eliya', 'hakgala-botanic-gardens', 'Hakgala Botanic Gardens', 'nature', 'hakgala_gardens',
     'An established hill-country botanic garden southeast of Nuwara Eliya, with terraced planting areas and plant collections.',
     'The garden is outside town; confirm current visiting information with the Department of National Botanic Gardens.'),
)
