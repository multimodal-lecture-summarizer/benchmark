"""Manual native-presentation decisions, reviewed 2026-10-19.

Indices address the immutable frame ledger, not requested timestamps. These
observations do not certify raw media, source edition, or complete source GT.
"""

# Event suffix -> (job number, last fully old frame, first changed frame).
# For hard cuts, the changed frame is also the first stable new frame.
HARD_CUTS = {
    'fast-dental-1': (1, 10, 11),
    'fast-dental-2': (2, 12, 13),
    'fast-dental-3': (2, 22, 23),
    'nbde-title-outline': (6, 15, 16),
    'nbde-outline-table': (7, 12, 13),
    'transformer-attention': (12, 12, 13),
    'rearranging-encoder': (13, 11, 12),
    'scapula-posterior-lateral': (14, 15, 16),
    'scapula-upper-limb': (15, 13, 14),
    'water-question': (20, 9, 10),
    'water-sports': (21, 12, 13),
    'fiber-protein': (22, 8, 9),
    'protein-structure': (23, 9, 10),
    'micronutrient-table': (24, 7, 8),
    'vitamin-solubility': (25, 7, 8),
    'cell-organelles': (26, 10, 11),
    'cell-supplements': (27, 10, 11),
    'optimization-title': (28, 13, 14),
    'optimization-agenda': (29, 9, 10),
    'adaptive-comparison': (30, 8, 9),
    'crossbite-appliance': (32, 10, 11),
    'appliance-crossbite': (33, 13, 14),
    'crossbite-return': (34, 14, 15),
    'skull-figure-build': (36, 10, 11),
    'skull-figure-return': (37, 9, 10),
    'skull-cranium': (37, 23, 24),
    'cranium-face': (38, 9, 10),
    'pediatric-outline': (42, 12, 13),
    'pediatric-question': (43, 15, 16),
    'clinical-endomembrane': (46, 9, 10),
    'endomembrane-diagram': (47, 13, 14),
    'caption-results': (55, 11, 12),
    'caption-automatic': (56, 12, 13),
}

MULTI_EVENT_KEYS = {
    '-a5-EHnZ_XA:5', '-a5-EHnZ_XA:6', '-a5-EHnZ_XA:7',
    'E_3gxQWaCoQ:24', 'E_3gxQWaCoQ:25', 'KDVP_WAIUXs:5',
}

UNRESOLVED_WINDOWS = {
    '2xr4P0WGKSA:0': (11, 'No instructional change in this finite title window. '
        'Annotation-to-event mapping remains unverified; window absence is not source-wide absence.'),
    '9GmySN5P408:24': (18, 'Final instructional page is unchanged throughout this window. '
        'No target point established; source-end annotation mapping remains unresolved.'),
    'ALRJCeVT0fQ:7': (19, 'Earlier muscle-to-motor-unit figure replacement and later terminal blank '
        'are distinct observations. No incoming slide appears before EOF. Original row cannot be '
        'assigned confidently to a primary replacement; no retiming inferred.'),
}

EFFECT_NOTES = {
    'colon-stool': 'Crossfade visibly mixes old and new content at inspected frames 6,7,8,9,21,22. '
        'Subtle first/last mixing cannot be certified from these lossy presentations. '
        'Independent review confirms frame0 fully old and frame35 stable new. '
        'Conservative observed onset bracket0..6 and completion bracket22..35 retained; timing HOLD. '
        'Earlier coarse last-old at1965.76 is superseded: native frame6 at1965.72 is already mixed.',
    'newborn-wipe': 'Full-size presentation inspection: frames11/12 clean old; '
        'frame13 first thin vertical black line; frame35 still has right-edge transition; '
        'frames36/37 clean stable new. Local point is last fully old frame12, not frame14.',
    'references-presenter': 'References page dissolves to presenter, an auxiliary outro, not '
        'an instructional replacement. Exclusion needs no primary timing point.',
    'presenter-credits': 'Presenter dissolves to copyright/credits, auxiliary outro. '
        'Exclusion needs no primary timing point.',
}
