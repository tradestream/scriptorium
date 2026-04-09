#!/usr/bin/env python3
"""
LITERARY ANALYZER
==================
A computational toolkit for close reading of poetry and literature,
detecting formal, sonic, figurative, structural, and thematic patterns
that shape how a text means.

Based on the methods described by:
  - John Ciardi (How Does a Poem Mean?, 1959)
  - Robert Pinsky (Singing School, 2013)
  - John Hollander (Rhyme's Reason, 1981)
  - Thomas C. Foster (How to Read Literature Like a Professor, 2003)
  - Thomas C. Foster (How to Read Poetry Like a Professor, 2018)
  - Shared methods from the Esoteric Writing Analyzer (Strauss, Rosen,
    Benardete, Melzer traditions)

ANALYSIS DOMAINS:
  I.   PROSODY & SOUND
    1.  Meter Detection — identify dominant metrical pattern and variations
    2.  Rhyme Scheme Mapping — end rhyme, internal rhyme, slant rhyme
    3.  Alliteration Detection — initial consonant repetition patterns
    4.  Assonance Detection — vowel sound recurrence across lines
    5.  Consonance Detection — consonant sound recurrence (non-initial)
    6.  Enjambment Analysis — line/sentence boundary tension
    7.  Caesura Detection — internal pauses within lines
    8.  Sound-Meaning Correspondence — onomatopoeia and phonesthetic patterns

  II.  FORM & STRUCTURE
    9.  Fixed Form Detection — sonnet, villanelle, sestina, ghazal, etc.
    10. Stanza Analysis — regularity, variation, grouping patterns
    11. Volta / Turn Detection — argumentative or tonal shifts
    12. Refrain & Repetition Tracking — recurring lines, anaphora, refrains
    13. Line-Length Patterning — syllabic/word count variation as structure
    14. Closure Analysis — how the text ends relative to how it begins

  III. FIGURATIVE LANGUAGE
    15. Metaphor & Simile Detection — figurative comparison identification
    16. Image Clustering — recurring sensory images grouped by domain
    17. Concrete vs. Abstract Ratio — specificity of vocabulary
    18. Symbol & Allegory Markers — objects/actions carrying layered meaning

  IV.  DICTION & VOCABULARY
    19. Anglo-Saxon vs. Latinate Ratio — etymological register
    20. Vocabulary Richness — type-token ratio, hapax legomena density
    21. Register Mixing — shifts between formal, colloquial, technical
    22. Parts of Speech Profile — noun/verb/adjective distributions

  V.   NARRATIVE & INTERTEXTUAL
    23. Archetype / Quest Pattern — mythic structure detection
    24. Biblical & Mythological Allusion — sacred/classical reference density
    25. Seasonal & Weather Symbolism — elemental symbolic patterns
    26. Intertextual Density — cross-reference and allusion markers

  VI.  SPEAKER & PERFORMANCE
    27. Dramatic Monologue Detection — persona, address, implied audience
    28. Apostrophe & Address — direct address to absent/abstract entities
    29. Tone Classification — emotional register via vocabulary analysis
    30. Persona vs. Poet Markers — signals of adopted voice

  VII. SHARED FROM ESOTERIC ANALYZER
    31. Contradiction Analysis — semantic tension between passages
    32. Irony Detection — sentiment inversion markers
    33. Silence & Omission — expected but absent topics/vocabulary
    34. Polysemy — words operating across multiple semantic domains
    35. Structural Symmetry — mirror/chiastic structures

MODES:
  analyzer.set_mode('poetry')  — prioritizes prosody, sound, form
  analyzer.set_mode('prose')   — prioritizes narrative, diction, figurative

Usage:
  analyzer = LiteraryAnalyzer()
  analyzer.load_text("path/to/text.txt")
  analyzer.set_mode('poetry')
  report = analyzer.full_analysis()
  analyzer.export_report("analysis_report.md")
  prompt = analyzer.generate_llm_prompt()
"""

import re
import math
import string
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk import pos_tag

# Ensure required NLTK data is available
for _res in ['punkt_tab', 'averaged_perceptron_tagger_eng', 'cmudict']:
    try:
        nltk.data.find(f'corpora/{_res}' if _res == 'cmudict'
                       else f'taggers/{_res}' if 'tagger' in _res
                       else f'tokenizers/{_res}')
    except (LookupError, OSError):
        nltk.download(_res, quiet=True)

from nltk.corpus import cmudict

# ---------------------------------------------------------------------------
# PHONETIC UTILITIES
# ---------------------------------------------------------------------------

CMU = cmudict.dict()


def get_phonemes(word: str) -> list:
    """Get CMU phoneme list for a word. Returns first pronunciation or []."""
    return CMU.get(word.lower(), [[]])[0]


def get_stresses(word: str) -> str:
    """Get stress pattern string for a word (0=no stress, 1=primary, 2=secondary)."""
    phones = get_phonemes(word)
    return ''.join(ch for ph in phones for ch in ph if ch.isdigit())


def syllable_count(word: str) -> int:
    """Count syllables using CMU dict, falling back to heuristic."""
    stresses = get_stresses(word)
    if stresses:
        return len(stresses)
    # Heuristic fallback
    word = word.lower().rstrip('e')
    count = max(1, len(re.findall(r'[aeiouy]+', word)))
    return count


def get_last_stressed_phonemes(word: str) -> list:
    """Get phonemes from the last stressed vowel onward (for rhyme detection)."""
    phones = get_phonemes(word)
    if not phones:
        return []
    # Find last stressed vowel
    for i in range(len(phones) - 1, -1, -1):
        if any(ch.isdigit() and ch != '0' for ch in phones[i]):
            return phones[i:]
    # If no primary stress, try any vowel
    for i in range(len(phones) - 1, -1, -1):
        if any(ch.isdigit() for ch in phones[i]):
            return phones[i:]
    return phones[-2:] if len(phones) >= 2 else phones


def strip_stress(phoneme: str) -> str:
    """Remove stress digits from a phoneme."""
    return ''.join(ch for ch in phoneme if not ch.isdigit())


def get_vowel_phonemes(word: str) -> list:
    """Extract vowel phonemes (stripped of stress) from a word."""
    phones = get_phonemes(word)
    return [strip_stress(p) for p in phones if any(ch.isdigit() for ch in p)]


def get_consonant_phonemes(word: str) -> list:
    """Extract consonant phonemes from a word."""
    phones = get_phonemes(word)
    return [p for p in phones if not any(ch.isdigit() for ch in p)]


def get_initial_consonant(word: str) -> str:
    """Get the initial consonant phoneme of a word."""
    phones = get_phonemes(word)
    if phones and not any(ch.isdigit() for ch in phones[0]):
        return phones[0]
    return word[0].upper() if word else ''


# Phonetic categories for sound-meaning analysis
PLOSIVES = {'P', 'B', 'T', 'D', 'K', 'G'}
FRICATIVES = {'F', 'V', 'TH', 'DH', 'S', 'Z', 'SH', 'ZH', 'HH'}
NASALS = {'M', 'N', 'NG'}
LIQUIDS = {'L', 'R'}
GLIDES = {'W', 'Y'}
SIBILANTS = {'S', 'Z', 'SH', 'ZH'}

# Latinate vs Anglo-Saxon suffixes (heuristic)
LATINATE_SUFFIXES = (
    'tion', 'sion', 'ment', 'ance', 'ence', 'ity', 'ous', 'ive',
    'able', 'ible', 'al', 'ual', 'ical', 'ious', 'eous', 'ular',
    'ular', 'ative', 'itive', 'ory', 'ary', 'ery',
)
ANGLO_SAXON_SUFFIXES = (
    'ness', 'ful', 'less', 'dom', 'ship', 'hood', 'like', 'wise',
    'ward', 'wards', 'ling', 'ish', 'ly', 'some', 'stead',
)

# Common monosyllabic Anglo-Saxon core words
ANGLO_SAXON_CORE = {
    'the', 'a', 'an', 'and', 'but', 'or', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'up', 'out', 'if', 'as', 'so', 'no',
    'not', 'all', 'can', 'had', 'has', 'her', 'him', 'his', 'how', 'its',
    'may', 'new', 'now', 'old', 'our', 'own', 'say', 'she', 'too', 'us',
    'man', 'day', 'eye', 'way', 'who', 'did', 'get', 'got', 'let', 'put',
    'run', 'set', 'sit', 'sun', 'war', 'dark', 'deep', 'free', 'good',
    'hard', 'high', 'home', 'king', 'land', 'life', 'long', 'love', 'mind',
    'name', 'night', 'sea', 'self', 'soul', 'time', 'word', 'work', 'world',
    'earth', 'water', 'fire', 'blood', 'bone', 'bread', 'death', 'dream',
    'flesh', 'ghost', 'heart', 'house', 'light', 'mouth', 'sleep', 'stone',
    'storm', 'sword', 'think', 'truth', 'wind', 'wood', 'year',
}

# ---------------------------------------------------------------------------
# SYMBOLIC / ALLUSION VOCABULARIES
# ---------------------------------------------------------------------------

BIBLICAL_VOCAB = {
    'eden', 'paradise', 'garden', 'fall', 'fallen', 'sin', 'grace',
    'redemption', 'salvation', 'baptism', 'crucifixion', 'resurrection',
    'cross', 'lamb', 'shepherd', 'serpent', 'flood', 'ark', 'covenant',
    'prophet', 'angel', 'devil', 'satan', 'god', 'lord', 'heaven', 'hell',
    'apostle', 'disciple', 'psalm', 'genesis', 'revelation', 'exodus',
    'wilderness', 'promised', 'commandment', 'forbidden', 'temple',
    'sacrifice', 'offering', 'bread', 'wine', 'communion', 'blessing',
    'curse', 'plague', 'miracle', 'prayer', 'sabbath', 'holy', 'sacred',
    'divine', 'eternal', 'immortal', 'soul', 'spirit', 'faith',
}

MYTHOLOGICAL_VOCAB = {
    'odyssey', 'odysseus', 'ulysses', 'zeus', 'athena', 'apollo',
    'aphrodite', 'ares', 'hermes', 'hades', 'persephone', 'orpheus',
    'prometheus', 'icarus', 'daedalus', 'narcissus', 'echo', 'siren',
    'cyclops', 'medusa', 'minotaur', 'labyrinth', 'phoenix', 'muse',
    'fate', 'fates', 'nemesis', 'titan', 'olympus', 'styx', 'lethe',
    'elysium', 'achilles', 'troy', 'trojan', 'helen', 'paris',
    'oedipus', 'sphinx', 'oracle', 'augury', 'omen', 'prophecy',
    'metamorphosis', 'nymph', 'satyr', 'centaur', 'ambrosia', 'nectar',
    'aeneas', 'virgil', 'homer', 'ovid', 'myth', 'mythic', 'heroic',
}

SEASONAL_ASSOCIATIONS = {
    'spring': {
        'bloom', 'blossom', 'bud', 'sprout', 'green', 'new', 'birth',
        'renew', 'renewal', 'fresh', 'young', 'youth', 'dawn', 'april',
        'may', 'thaw', 'melt', 'robin', 'swallow', 'crocus', 'daffodil',
    },
    'summer': {
        'sun', 'heat', 'hot', 'warm', 'golden', 'ripe', 'harvest',
        'zenith', 'noon', 'blaze', 'burn', 'sweat', 'lazy', 'abundance',
        'june', 'july', 'august', 'meadow', 'bee', 'rose', 'full',
    },
    'autumn': {
        'fall', 'leaf', 'leaves', 'wither', 'decay', 'decline', 'amber',
        'rust', 'brown', 'harvest', 'reap', 'gather', 'twilight', 'dusk',
        'september', 'october', 'november', 'bare', 'wind', 'chill',
    },
    'winter': {
        'cold', 'frost', 'freeze', 'ice', 'snow', 'bare', 'barren',
        'death', 'dead', 'dark', 'darkness', 'night', 'sleep', 'silent',
        'december', 'january', 'february', 'stark', 'bleak', 'pale',
    },
}

WEATHER_VOCAB = {
    'rain': {'rain', 'shower', 'drizzle', 'downpour', 'deluge', 'flood',
             'wet', 'drenched', 'soaked', 'puddle', 'stream', 'weep'},
    'storm': {'storm', 'thunder', 'lightning', 'tempest', 'hurricane',
              'tornado', 'gale', 'whirlwind', 'rage', 'fury', 'violent'},
    'fog': {'fog', 'mist', 'haze', 'murky', 'obscure', 'dim', 'veil',
            'shroud', 'unclear', 'confusion', 'lost'},
    'sun': {'sun', 'sunshine', 'bright', 'radiant', 'gleam', 'shine',
            'golden', 'warm', 'light', 'illuminate', 'glory', 'clear'},
    'snow': {'snow', 'white', 'blank', 'pure', 'cold', 'silence',
             'still', 'cover', 'drift', 'flake', 'crystal', 'freeze'},
}

# Archetype vocabularies (Foster)
QUEST_VOCAB = {
    'quest', 'journey', 'seek', 'search', 'find', 'discover', 'wander',
    'travel', 'road', 'path', 'way', 'gate', 'door', 'threshold',
    'trial', 'test', 'ordeal', 'challenge', 'obstacle', 'dragon',
    'treasure', 'grail', 'home', 'return', 'hero', 'call', 'adventure',
    'crossing', 'bridge', 'river', 'mountain', 'valley', 'forest',
    'labyrinth', 'maze', 'guide', 'mentor', 'companion', 'stranger',
}

COMMUNION_VOCAB = {
    'eat', 'drink', 'feast', 'meal', 'bread', 'wine', 'table',
    'share', 'gather', 'host', 'guest', 'toast', 'cup', 'plate',
    'hunger', 'thirst', 'nourish', 'feed', 'supper', 'dinner',
    'breakfast', 'banquet', 'communion', 'sacrament', 'offering',
}

# Tone vocabulary clusters
TONE_CLUSTERS = {
    'elegiac': {
        'loss', 'gone', 'past', 'memory', 'remember', 'once', 'ago',
        'mourn', 'grieve', 'sorrow', 'lament', 'weep', 'tear', 'fade',
        'vanish', 'disappear', 'ghost', 'shadow', 'dust', 'ashes',
        'grave', 'tomb', 'never', 'no more', 'farewell', 'departed',
    },
    'celebratory': {
        'joy', 'rejoice', 'celebrate', 'praise', 'glory', 'triumph',
        'exult', 'sing', 'dance', 'bright', 'radiant', 'splendid',
        'magnificent', 'beautiful', 'wonderful', 'blessed', 'happy',
    },
    'meditative': {
        'think', 'consider', 'wonder', 'ponder', 'contemplate', 'muse',
        'reflect', 'perhaps', 'maybe', 'seems', 'appears', 'might',
        'quietly', 'still', 'silence', 'pause', 'slow', 'gaze',
    },
    'urgent': {
        'now', 'must', 'quick', 'fast', 'hurry', 'run', 'flee',
        'before', 'while', 'seize', 'grasp', 'take', 'come', 'go',
        'haste', 'press', 'rush', 'soon', 'immediately', 'sudden',
    },
    'ironic': {
        'of course', 'naturally', 'surely', 'certainly', 'indeed',
        'no doubt', 'clearly', 'obviously', 'everybody knows',
        'needless to say', 'as everyone agrees', 'it goes without saying',
    },
    'passionate': {
        'love', 'desire', 'burn', 'fire', 'flame', 'heart', 'kiss',
        'embrace', 'touch', 'ache', 'yearn', 'long', 'tremble',
        'intoxicate', 'mad', 'wild', 'fever', 'heat', 'blood',
    },
}

# ---------------------------------------------------------------------------
# LITERARY ANALYZER CLASS
# ---------------------------------------------------------------------------


class LiteraryAnalyzer:
    """
    Comprehensive literary and poetic analysis toolkit.

    Modes:
      'poetry' — prioritizes prosody, sound, form, figurative language
      'prose'  — prioritizes narrative, diction, intertextual, speaker
    """

    def __init__(self):
        self.text = ''
        self.title = ''
        self.mode = 'poetry'  # default
        self.lines = []       # lines of text (preserving line breaks)
        self.words = []       # all word tokens
        self.sentences = []   # sentence-tokenized text
        self.paragraphs = []  # paragraph-split text
        self.stanzas = []     # stanza-split text (poetry: blank-line separated)
        self.chapters = []    # chapter-split text (prose)
        self.results = {}
        self.expected_topics = []

    def set_mode(self, mode: str):
        """Set analysis mode: 'poetry' or 'prose'."""
        if mode not in ('poetry', 'prose'):
            raise ValueError("Mode must be 'poetry' or 'prose'")
        self.mode = mode

    def load_text(self, filepath: str, title: Optional[str] = None):
        """Load text from a file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            self.text = f.read()
        self.title = title or filepath.split('/')[-1].rsplit('.', 1)[0]
        self._parse()

    def load_text_string(self, text: str, title: str = "Untitled"):
        """Load text from a string."""
        self.text = text
        self.title = title
        self._parse()

    def set_expected_topics(self, topics: list):
        """Set topics expected but potentially absent (for silence analysis)."""
        self.expected_topics = topics

    def _parse(self):
        """Parse text into lines, words, sentences, paragraphs, stanzas."""
        if hasattr(self, '_parsed') and self._parsed:
            return  # Already parsed — skip expensive re-tokenization

        # Lines (preserving original line breaks)
        self.lines = [line for line in self.text.split('\n') if line.strip()]

        # Words
        self.words = word_tokenize(self.text)

        # Sentences
        self.sentences = sent_tokenize(self.text)

        # Paragraphs (double newline separated)
        raw_paras = re.split(r'\n\s*\n', self.text)
        self.paragraphs = [p.strip() for p in raw_paras if p.strip()]

        # Stanzas (for poetry: blank-line separated groups of lines)
        self.stanzas = []
        current_stanza = []
        for line in self.text.split('\n'):
            if line.strip():
                current_stanza.append(line.strip())
            elif current_stanza:
                self.stanzas.append(current_stanza)
                current_stanza = []
        if current_stanza:
            self.stanzas.append(current_stanza)

        # Chapters (for prose: heading-based or large section breaks)
        self.chapters = []
        chapter_pattern = re.compile(
            r'^(?:Chapter|CHAPTER|Part|PART|Book|BOOK|Section|SECTION)'
            r'\s+[\dIVXLCDMivxlcdm]+',
            re.MULTILINE,
        )
        splits = chapter_pattern.split(self.text)
        titles = chapter_pattern.findall(self.text)
        if len(splits) > 1:
            for i, section in enumerate(splits[1:], 1):
                self.chapters.append({
                    'title': titles[i - 1].strip() if i - 1 < len(titles) else f'Section {i}',
                    'text': section.strip(),
                })
        else:
            # Fall back to paragraphs as "chapters" for short texts
            self.chapters = [{'title': f'Section {i+1}', 'text': p}
                             for i, p in enumerate(self.paragraphs)]

        self._parsed = True

    # ==================================================================
    # I. PROSODY & SOUND
    # ==================================================================

    def analyze_meter(self) -> dict:
        """
        METHOD: Meter Detection
        SOURCES: Hollander (Rhyme's Reason), Ciardi (How Does a Poem Mean),
                 Foster (How to Read Poetry Like a Professor)

        Detect the dominant metrical pattern and significant variations.
        Uses CMU Pronouncing Dictionary for stress assignment.
        """
        if not self.lines:
            return {'score': 0, 'method': 'Meter Detection'}

        line_analyses = []
        foot_type_counts = Counter()
        feet_per_line = []

        for line in self.lines:
            words_in_line = [w for w in word_tokenize(line) if w.isalpha()]
            if not words_in_line:
                continue

            # Build stress string for the line
            stress_string = ''
            for w in words_in_line:
                s = get_stresses(w)
                if s:
                    stress_string += s
                else:
                    # Heuristic: monosyllables get stress 1
                    sc = syllable_count(w)
                    stress_string += '1' if sc == 1 else '10' * (sc // 2) + ('1' if sc % 2 else '')

            # Count syllables
            total_syllables = len(stress_string)

            # Detect feet (simplified: iambic=01, trochaic=10, anapestic=001,
            # dactylic=100, spondaic=11, pyrrhic=00)
            feet = []
            i = 0
            while i < len(stress_string):
                remaining = stress_string[i:]
                if len(remaining) >= 3:
                    tri = remaining[:3]
                    if tri in ('001', '002'):
                        feet.append('anapest')
                        i += 3
                        continue
                    elif tri in ('100', '200'):
                        feet.append('dactyl')
                        i += 3
                        continue
                if len(remaining) >= 2:
                    di = remaining[:2]
                    stressed = di.replace('2', '1')
                    if stressed == '01':
                        feet.append('iamb')
                    elif stressed == '10':
                        feet.append('trochee')
                    elif stressed == '11':
                        feet.append('spondee')
                    elif stressed == '00':
                        feet.append('pyrrhic')
                    else:
                        feet.append('unknown')
                    i += 2
                else:
                    i += 1

            for f in feet:
                foot_type_counts[f] += 1
            feet_per_line.append(len(feet))

            line_analyses.append({
                'line': line.strip()[:80],
                'stress_pattern': stress_string,
                'syllable_count': total_syllables,
                'feet': feet,
                'foot_count': len(feet),
            })

        if not line_analyses:
            return {'score': 0, 'method': 'Meter Detection'}

        # Determine dominant foot type
        total_feet = sum(foot_type_counts.values())
        dominant_foot = foot_type_counts.most_common(1)[0] if foot_type_counts else ('unknown', 0)
        dominance_ratio = dominant_foot[1] / max(total_feet, 1)

        # Determine dominant line length
        avg_feet = sum(feet_per_line) / max(len(feet_per_line), 1)
        length_names = {
            1: 'monometer', 2: 'dimeter', 3: 'trimeter', 4: 'tetrameter',
            5: 'pentameter', 6: 'hexameter', 7: 'heptameter', 8: 'octameter',
        }
        dominant_length = length_names.get(round(avg_feet), f'{round(avg_feet)}-foot')

        # Regularity score: how consistent is the meter?
        feet_variance = sum((f - avg_feet) ** 2 for f in feet_per_line) / max(len(feet_per_line), 1)
        regularity = max(0, 1 - feet_variance / max(avg_feet, 1))

        # Score: strong meter = high dominance + high regularity
        score = min(1.0, dominance_ratio * 0.6 + regularity * 0.4)

        # Find lines with metrical variation (substitutions)
        variations = []
        for la in line_analyses:
            non_dominant = [f for f in la['feet'] if f != dominant_foot[0]]
            if non_dominant and la['foot_count'] >= 3:
                variations.append({
                    'line': la['line'],
                    'substitutions': non_dominant,
                    'foot_count': la['foot_count'],
                })

        return {
            'score': round(score, 3),
            'method': 'Meter Detection (Hollander/Ciardi/Foster)',
            'dominant_foot': dominant_foot[0],
            'dominant_foot_ratio': round(dominance_ratio, 3),
            'foot_type_distribution': dict(foot_type_counts.most_common()),
            'average_feet_per_line': round(avg_feet, 2),
            'dominant_line_length': dominant_length,
            'metrical_regularity': round(regularity, 3),
            'total_lines_analyzed': len(line_analyses),
            'metrical_variations': variations[:10],
            'syllable_counts': [la['syllable_count'] for la in line_analyses],
            'precedent': (
                "Hollander: 'meter is a system of binary oppositions between'  "
                "prominent and non-prominent syllables. Ciardi: the effect comes "
                "from variation against the established norm. Foster: deviations "
                "from the base pattern are where the meaning lives."
            ),
            'interpretation': (
                f"Dominant pattern: {dominant_foot[0]} {dominant_length} "
                f"({dominance_ratio:.0%} of feet). "
                f"{'High' if regularity > 0.7 else 'Moderate' if regularity > 0.4 else 'Low'} "
                f"metrical regularity. Variations from the base pattern signal "
                f"emphasis, emotional shift, or deliberate expressive disruption."
            ),
        }

    def analyze_rhyme_scheme(self) -> dict:
        """
        METHOD: Rhyme Scheme Mapping
        SOURCES: Hollander (Rhyme's Reason), Foster (How to Read Poetry)

        Map end rhymes, detect internal rhymes, and classify rhyme quality.
        """
        if not self.lines:
            return {'score': 0, 'method': 'Rhyme Scheme Mapping'}

        # Extract last word of each line
        line_end_words = []
        for line in self.lines:
            words = [w.lower() for w in word_tokenize(line) if w.isalpha()]
            line_end_words.append(words[-1] if words else '')

        # Build rhyme groups using phonetic comparison
        rhyme_labels = {}
        current_label = 0
        label_map = {}  # end_phonemes -> label

        scheme = []
        for i, word in enumerate(line_end_words):
            if not word:
                scheme.append('-')
                continue

            rhyme_phones = get_last_stressed_phonemes(word)
            rhyme_key = tuple(strip_stress(p) for p in rhyme_phones)

            if rhyme_key and len(rhyme_key) > 0:
                # Check for exact match
                matched = False
                for existing_key, label in label_map.items():
                    if rhyme_key == existing_key and word != line_end_words[label]:
                        scheme.append(chr(65 + label))
                        matched = True
                        break
                if not matched:
                    # Check for slant rhyme (shared vowel, different consonant)
                    slant_matched = False
                    for existing_key, label in label_map.items():
                        if (len(rhyme_key) > 0 and len(existing_key) > 0
                                and rhyme_key[0] == existing_key[0]
                                and word != line_end_words[label]):
                            scheme.append(chr(65 + label).lower())  # lowercase = slant
                            slant_matched = True
                            break
                    if not slant_matched:
                        label_map[rhyme_key] = current_label
                        scheme.append(chr(65 + current_label))
                        current_label += 1
            else:
                scheme.append('-')

        scheme_str = ''.join(scheme[:40])

        # Count rhyming line pairs
        rhyme_pairs = 0
        for i in range(len(scheme)):
            for j in range(i + 1, len(scheme)):
                if scheme[i].upper() == scheme[j].upper() and scheme[i] != '-':
                    rhyme_pairs += 1
                    break

        total_lines = len(self.lines)
        rhyme_density = rhyme_pairs / max(total_lines, 1)

        # Detect internal rhymes
        internal_rhymes = []
        for i, line in enumerate(self.lines):
            words = [w.lower() for w in word_tokenize(line) if w.isalpha()]
            if len(words) < 4:
                continue
            mid = len(words) // 2
            for w1 in words[:mid]:
                for w2 in words[mid:]:
                    rp1 = get_last_stressed_phonemes(w1)
                    rp2 = get_last_stressed_phonemes(w2)
                    if (rp1 and rp2
                            and tuple(strip_stress(p) for p in rp1) == tuple(strip_stress(p) for p in rp2)
                            and w1 != w2):
                        internal_rhymes.append({
                            'line': i + 1,
                            'words': (w1, w2),
                        })

        # Detect common schemes
        detected_form = 'free verse'
        if len(scheme) >= 14:
            s14 = ''.join(s.upper() for s in scheme[:14])
            if s14[:8].count(s14[0]) >= 3 and s14[:8].count(s14[1]) >= 3:
                detected_form = 'possible Petrarchan sonnet'
            elif len(set(scheme[:4])) <= 3 and scheme[0] != scheme[1]:
                detected_form = 'possible Shakespearean sonnet'

        # Check for couplets
        couplet_count = sum(1 for i in range(0, len(scheme) - 1, 2)
                           if scheme[i].upper() == scheme[i + 1].upper() and scheme[i] != '-')
        if couplet_count > len(scheme) // 4:
            detected_form = 'couplet-dominant'

        score = min(1.0, rhyme_density * 2 + len(internal_rhymes) * 0.05)

        return {
            'score': round(score, 3),
            'method': 'Rhyme Scheme Mapping (Hollander/Foster)',
            'scheme_string': scheme_str,
            'rhyme_density': round(rhyme_density, 3),
            'rhyme_pairs': rhyme_pairs,
            'internal_rhymes': internal_rhymes[:10],
            'internal_rhyme_count': len(internal_rhymes),
            'detected_form': detected_form,
            'total_unique_rhyme_sounds': current_label,
            'precedent': (
                "Hollander: Rhyme scheme is the skeleton of form; it creates "
                "expectation and satisfaction. Slant rhymes signal modernity, "
                "irony, or unresolved tension. Internal rhymes create secondary "
                "rhythmic layers."
            ),
            'interpretation': (
                f"Rhyme scheme: {scheme_str}. "
                f"{'Dense' if rhyme_density > 0.5 else 'Moderate' if rhyme_density > 0.2 else 'Sparse'} "
                f"end-rhyme ({rhyme_density:.0%} of lines). "
                f"{len(internal_rhymes)} internal rhyme(s) detected. "
                f"Form signal: {detected_form}."
            ),
        }

    def analyze_alliteration(self) -> dict:
        """
        METHOD: Alliteration Detection
        SOURCES: Pinsky (Singing School), Hollander (Rhyme's Reason),
                 Ciardi (How Does a Poem Mean)

        Detect initial consonant repetition patterns across lines.
        """
        line_scores = []
        alliterative_lines = []

        for i, line in enumerate(self.lines):
            words = [w for w in word_tokenize(line) if w.isalpha() and len(w) > 1]
            if len(words) < 3:
                line_scores.append(0)
                continue

            initials = [get_initial_consonant(w) for w in words]
            initial_counts = Counter(initials)
            # Score: proportion of words sharing initial consonant with at least one other
            repeated = sum(c for c in initial_counts.values() if c > 1)
            ratio = repeated / max(len(words), 1)
            line_scores.append(ratio)

            if ratio > 0.4:
                dominant = initial_counts.most_common(1)[0]
                alliterative_lines.append({
                    'line_number': i + 1,
                    'line': line.strip()[:100],
                    'dominant_sound': dominant[0],
                    'count': dominant[1],
                    'ratio': round(ratio, 3),
                })

        avg_score = sum(line_scores) / max(len(line_scores), 1)
        score = min(1.0, avg_score * 3)

        return {
            'score': round(score, 3),
            'method': 'Alliteration Detection (Pinsky/Hollander/Ciardi)',
            'average_alliteration_ratio': round(avg_score, 4),
            'alliterative_lines': sorted(alliterative_lines,
                                         key=lambda x: x['ratio'], reverse=True)[:10],
            'total_alliterative_lines': len(alliterative_lines),
            'precedent': (
                "Pinsky: Consonant patterns create 'braiding' effects that link "
                "words beyond their semantic connections. Ciardi: alliteration can "
                "accelerate or impede pace depending on the consonant type."
            ),
            'interpretation': (
                f"{'Strong' if avg_score > 0.3 else 'Moderate' if avg_score > 0.15 else 'Light'} "
                f"alliterative texture. {len(alliterative_lines)} lines with notable "
                f"initial consonant repetition."
            ),
        }

    def analyze_assonance(self) -> dict:
        """
        METHOD: Assonance Detection
        SOURCES: Pinsky (Singing School), Hollander (Rhyme's Reason)

        Detect vowel sound recurrence patterns across and within lines.
        """
        line_vowel_profiles = []
        assonant_lines = []

        for i, line in enumerate(self.lines):
            words = [w.lower() for w in word_tokenize(line) if w.isalpha()]
            if len(words) < 3:
                continue

            vowels = []
            for w in words:
                vowels.extend(get_vowel_phonemes(w))

            if len(vowels) < 3:
                continue

            vowel_counts = Counter(vowels)
            dominant = vowel_counts.most_common(1)[0] if vowel_counts else ('', 0)
            repetition_ratio = dominant[1] / max(len(vowels), 1)

            line_vowel_profiles.append({
                'line_number': i + 1,
                'vowel_distribution': dict(vowel_counts.most_common(5)),
                'dominant_vowel': dominant[0],
                'repetition_ratio': repetition_ratio,
            })

            if repetition_ratio > 0.35:
                assonant_lines.append({
                    'line_number': i + 1,
                    'line': self.lines[i].strip()[:100],
                    'dominant_vowel': dominant[0],
                    'repetition_ratio': round(repetition_ratio, 3),
                })

        avg_ratio = (sum(p['repetition_ratio'] for p in line_vowel_profiles)
                     / max(len(line_vowel_profiles), 1))
        score = min(1.0, avg_ratio * 3)

        return {
            'score': round(score, 3),
            'method': 'Assonance Detection (Pinsky/Hollander)',
            'average_vowel_repetition': round(avg_ratio, 4),
            'assonant_lines': sorted(assonant_lines,
                                     key=lambda x: x['repetition_ratio'], reverse=True)[:10],
            'total_assonant_lines': len(assonant_lines),
            'precedent': (
                "Pinsky: Vowel patterns create 'changes of key' like music. "
                "Hollander: Assonance is the 'spirit of rhyme' — it links words "
                "without the closure of full rhyme."
            ),
            'interpretation': (
                f"{'Rich' if avg_ratio > 0.3 else 'Moderate' if avg_ratio > 0.2 else 'Subtle'} "
                f"vowel patterning. {len(assonant_lines)} lines with notable assonance."
            ),
        }

    def analyze_consonance(self) -> dict:
        """
        METHOD: Consonance Detection
        SOURCES: Pinsky (Singing School), Foster (How to Read Poetry)

        Detect non-initial consonant sound repetition and classify by
        phonetic type (plosive, fricative, nasal, liquid).
        """
        consonant_totals = Counter()
        type_totals = Counter()

        for line in self.lines:
            words = [w.lower() for w in word_tokenize(line) if w.isalpha()]
            for w in words:
                consonants = get_consonant_phonemes(w)
                for c in consonants:
                    consonant_totals[c] += 1
                    if c in PLOSIVES:
                        type_totals['plosive'] += 1
                    elif c in FRICATIVES:
                        type_totals['fricative'] += 1
                    elif c in NASALS:
                        type_totals['nasal'] += 1
                    elif c in LIQUIDS:
                        type_totals['liquid'] += 1
                    elif c in SIBILANTS:
                        type_totals['sibilant'] += 1

        total = sum(type_totals.values()) or 1
        type_profile = {k: round(v / total, 3) for k, v in type_totals.most_common()}

        # Dominant consonant texture
        dominant_type = type_totals.most_common(1)[0][0] if type_totals else 'none'
        texture_map = {
            'plosive': 'percussive/sharp',
            'fricative': 'flowing/hissing',
            'nasal': 'resonant/humming',
            'liquid': 'smooth/flowing',
            'sibilant': 'whispering/sibilant',
        }
        texture = texture_map.get(dominant_type, 'neutral')

        # Score based on consonant clustering (high repetition = more textured)
        top_consonant = consonant_totals.most_common(1)[0] if consonant_totals else ('', 0)
        clustering = top_consonant[1] / max(sum(consonant_totals.values()), 1)
        score = min(1.0, clustering * 5 + (1 - len(consonant_totals) / 25) * 0.3)

        return {
            'score': round(score, 3),
            'method': 'Consonance Detection (Pinsky/Foster)',
            'consonant_type_profile': type_profile,
            'dominant_texture': texture,
            'top_consonants': dict(consonant_totals.most_common(10)),
            'precedent': (
                "Pinsky: Tracking which physical mouth positions create sounds "
                "reveals the poem's bodily dimension. Ciardi: Consonant clusters "
                "impede reading, creating resistance and slowness; open consonants "
                "accelerate."
            ),
            'interpretation': (
                f"Dominant consonant texture: {texture}. "
                f"Profile: {', '.join(f'{k} {v:.0%}' for k, v in type_profile.items())}."
            ),
        }

    def analyze_enjambment(self) -> dict:
        """
        METHOD: Enjambment Analysis
        SOURCES: Pinsky (Singing School), Hollander (Rhyme's Reason),
                 Foster (How to Read Poetry), Ciardi (How Does a Poem Mean)

        Detect line/sentence boundary tension: where sentences cross line breaks.
        """
        if len(self.lines) < 2:
            return {'score': 0, 'method': 'Enjambment Analysis'}

        enjambed = []
        end_stopped = 0
        total = 0

        for i, line in enumerate(self.lines):
            stripped = line.rstrip()
            if not stripped:
                continue
            total += 1

            last_char = stripped[-1]
            # End-stopped: line ends with terminal punctuation
            if last_char in '.!?;:':
                end_stopped += 1
            # Enjambed: line ends without terminal punctuation
            elif last_char not in ',':
                # Strong enjambment: line ends mid-phrase
                words = word_tokenize(stripped)
                if words:
                    last_word = words[-1].lower()
                    # Very strong enjambment indicators
                    strong = last_word in ('the', 'a', 'an', 'of', 'in', 'to',
                                           'and', 'or', 'but', 'with', 'by',
                                           'for', 'not', 'no', 'my', 'your',
                                           'his', 'her', 'its', 'our', 'their')
                    enjambed.append({
                        'line_number': i + 1,
                        'line': stripped[:80],
                        'strength': 'strong' if strong else 'moderate',
                    })

        enjambment_ratio = len(enjambed) / max(total, 1)
        end_stop_ratio = end_stopped / max(total, 1)

        score = min(1.0, enjambment_ratio * 1.5)

        return {
            'score': round(score, 3),
            'method': 'Enjambment Analysis (Pinsky/Hollander/Foster/Ciardi)',
            'enjambment_ratio': round(enjambment_ratio, 3),
            'end_stop_ratio': round(end_stop_ratio, 3),
            'enjambed_lines': enjambed[:15],
            'total_enjambed': len(enjambed),
            'strong_enjambments': sum(1 for e in enjambed if e['strength'] == 'strong'),
            'precedent': (
                "Pinsky: The tension between line and sentence is the heartbeat "
                "of verse. Hollander: Enjambment creates 'semantic suspension' — "
                "meaning is held across the line break. Foster: Follow the sentence, "
                "not the line, to find the meaning."
            ),
            'interpretation': (
                f"{'Heavy' if enjambment_ratio > 0.5 else 'Moderate' if enjambment_ratio > 0.25 else 'Light'} "
                f"enjambment ({enjambment_ratio:.0%} of lines run on). "
                f"{sum(1 for e in enjambed if e['strength'] == 'strong')} strong enjambments "
                f"(line breaks mid-phrase). "
                f"{'Highly end-stopped' if end_stop_ratio > 0.6 else 'Mixed' if end_stop_ratio > 0.3 else 'Flowing'} "
                f"overall texture."
            ),
        }

    def analyze_caesura(self) -> dict:
        """
        METHOD: Caesura Detection
        SOURCES: Hollander (Rhyme's Reason), Ciardi (How Does a Poem Mean)

        Detect internal pauses within lines.
        """
        caesura_lines = []
        total_caesuras = 0

        for i, line in enumerate(self.lines):
            stripped = line.strip()
            if not stripped or len(stripped) < 10:
                continue

            # Find internal punctuation that creates pause
            pauses = [(m.start(), m.group()) for m in
                      re.finditer(r'[,;:\-—–]|\.\.\.|[!?](?!$)', stripped)]

            if pauses:
                total_caesuras += len(pauses)
                # Calculate position of primary caesura relative to line length
                primary = pauses[len(pauses) // 2]
                position_ratio = primary[0] / max(len(stripped), 1)
                caesura_lines.append({
                    'line_number': i + 1,
                    'line': stripped[:80],
                    'caesura_count': len(pauses),
                    'primary_position': round(position_ratio, 2),
                    'mark': primary[1],
                })

        caesura_ratio = len(caesura_lines) / max(len(self.lines), 1)
        # Medial caesura score: how often does the primary caesura fall near center?
        medial_count = sum(1 for c in caesura_lines if 0.3 <= c['primary_position'] <= 0.7)
        medial_ratio = medial_count / max(len(caesura_lines), 1)

        score = min(1.0, caesura_ratio * 1.2 + medial_ratio * 0.3)

        return {
            'score': round(score, 3),
            'method': 'Caesura Detection (Hollander/Ciardi)',
            'caesura_ratio': round(caesura_ratio, 3),
            'medial_caesura_ratio': round(medial_ratio, 3),
            'total_caesuras': total_caesuras,
            'caesura_lines': caesura_lines[:15],
            'precedent': (
                "Hollander: The alexandrine is typically caesura'd at midpoint. "
                "Ciardi: Caesura is one of the non-metrical devices that impede "
                "pace and create rhythmic variety."
            ),
            'interpretation': (
                f"{caesura_ratio:.0%} of lines contain internal pauses. "
                f"{medial_ratio:.0%} of caesuras fall near the line's center "
                f"(medial position). "
                f"{'Regular, structured pausing' if medial_ratio > 0.5 else 'Variable pause placement'}."
            ),
        }

    def analyze_sound_meaning(self) -> dict:
        """
        METHOD: Sound-Meaning Correspondence
        SOURCES: Ciardi (How Does a Poem Mean), Pinsky (Singing School),
                 Foster (How to Read Poetry)

        Detect phonesthetic patterns: cases where sound quality
        corresponds to semantic content (onomatopoeia and beyond).
        """
        # Onomatopoeia vocabulary
        onomatopoeia = {
            'buzz', 'hiss', 'crash', 'bang', 'crack', 'snap', 'pop',
            'sizzle', 'murmur', 'whisper', 'roar', 'thunder', 'splash',
            'drip', 'trickle', 'gurgle', 'babble', 'rustle', 'hum',
            'drone', 'clang', 'clatter', 'rattle', 'thud', 'thump',
            'whoosh', 'swoosh', 'screech', 'shriek', 'wail', 'moan',
            'groan', 'sigh', 'gasp', 'pant', 'clink', 'chime', 'toll',
            'ring', 'echo', 'boom', 'rumble', 'creak', 'squeak', 'crunch',
            'plop', 'splatter', 'fizz', 'whir', 'click', 'tick', 'tock',
        }

        all_words_lower = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words_lower), 1)

        # Count onomatopoeia
        ono_hits = sum(1 for w in all_words_lower if w in onomatopoeia)
        ono_density = ono_hits / total

        # Analyze phonesthetic texture per stanza/paragraph
        unit_textures = []
        units = self.stanzas if self.mode == 'poetry' else self.paragraphs
        for idx, unit in enumerate(units[:50]):
            unit_text = ' '.join(unit) if isinstance(unit, list) else unit
            unit_words = [w.lower() for w in word_tokenize(unit_text) if w.isalpha()]
            if len(unit_words) < 5:
                continue

            consonants = []
            for w in unit_words:
                consonants.extend(get_consonant_phonemes(w))

            c_counter = Counter(consonants)
            c_total = sum(c_counter.values()) or 1

            plosive_ratio = sum(c_counter.get(p, 0) for p in PLOSIVES) / c_total
            fricative_ratio = sum(c_counter.get(p, 0) for p in FRICATIVES) / c_total
            liquid_ratio = sum(c_counter.get(p, 0) for p in LIQUIDS) / c_total
            nasal_ratio = sum(c_counter.get(p, 0) for p in NASALS) / c_total

            if plosive_ratio > 0.4:
                texture = 'percussive/harsh'
            elif fricative_ratio > 0.35:
                texture = 'flowing/sibilant'
            elif liquid_ratio > 0.2:
                texture = 'smooth/liquid'
            elif nasal_ratio > 0.2:
                texture = 'resonant/humming'
            else:
                texture = 'balanced'

            unit_textures.append({
                'unit': idx + 1,
                'texture': texture,
                'plosive': round(plosive_ratio, 3),
                'fricative': round(fricative_ratio, 3),
                'liquid': round(liquid_ratio, 3),
                'nasal': round(nasal_ratio, 3),
            })

        score = min(1.0, ono_density * 20 + (len(set(t['texture'] for t in unit_textures)) > 2) * 0.3)

        return {
            'score': round(score, 3),
            'method': 'Sound-Meaning Correspondence (Ciardi/Pinsky/Foster)',
            'onomatopoeia_density': round(ono_density, 5),
            'onomatopoeia_count': ono_hits,
            'unit_textures': unit_textures[:10],
            'texture_variety': len(set(t['texture'] for t in unit_textures)),
            'precedent': (
                "Ciardi: Sound is not merely auditory but physically embodied; "
                "plosives bounce, fricatives flow, liquids smooth. Pinsky: "
                "Tracking mouth positions reveals the poem's bodily dimension."
            ),
            'interpretation': (
                f"{ono_hits} onomatopoeic words detected. "
                f"{len(set(t['texture'] for t in unit_textures))} distinct sonic textures "
                f"across units, suggesting {'rich' if len(set(t['texture'] for t in unit_textures)) > 2 else 'uniform'} "
                f"sound-meaning interplay."
            ),
        }

    # ==================================================================
    # II. FORM & STRUCTURE
    # ==================================================================

    def analyze_fixed_form(self) -> dict:
        """
        METHOD: Fixed Form Detection
        SOURCES: Hollander (Rhyme's Reason), Foster (How to Read Poetry)

        Identify whether the text matches a known poetic form:
        sonnet, villanelle, sestina, haiku, ghazal, pantoum, ballad, etc.
        """
        total_lines = len(self.lines)
        stanza_count = len(self.stanzas)
        stanza_lengths = [len(s) for s in self.stanzas]

        detected_forms = []
        confidence_scores = {}

        # --- SONNET (14 lines) ---
        if total_lines == 14 or (13 <= total_lines <= 15):
            confidence_scores['sonnet'] = 0.7 if total_lines == 14 else 0.3
            # Check for octave/sestet or quatrain/couplet structure
            if stanza_count == 2 and stanza_lengths == [8, 6]:
                detected_forms.append('Petrarchan sonnet (octave + sestet)')
                confidence_scores['sonnet'] = 0.9
            elif stanza_count == 4 and stanza_lengths == [4, 4, 4, 2]:
                detected_forms.append('Shakespearean sonnet (3 quatrains + couplet)')
                confidence_scores['sonnet'] = 0.9
            elif stanza_count == 5 and stanza_lengths == [4, 4, 4, 2]:
                detected_forms.append('Possible Shakespearean sonnet')
                confidence_scores['sonnet'] = 0.6
            else:
                detected_forms.append('Sonnet (14 lines, non-standard stanza division)')

        # --- HAIKU (3 lines, 5-7-5 syllables) ---
        if total_lines == 3:
            syllables = [sum(syllable_count(w) for w in word_tokenize(l) if w.isalpha())
                         for l in self.lines]
            if syllables == [5, 7, 5]:
                detected_forms.append('Haiku (5-7-5)')
                confidence_scores['haiku'] = 0.95
            elif abs(syllables[0] - 5) <= 1 and abs(syllables[1] - 7) <= 1 and abs(syllables[2] - 5) <= 1:
                detected_forms.append(f'Near-haiku ({syllables[0]}-{syllables[1]}-{syllables[2]})')
                confidence_scores['haiku'] = 0.5

        # --- VILLANELLE (19 lines: 5 tercets + 1 quatrain, 2 refrains) ---
        if total_lines == 19 and stanza_count == 6:
            tercet_check = all(l == 3 for l in stanza_lengths[:5])
            quatrain_check = stanza_lengths[5] == 4
            if tercet_check and quatrain_check:
                # Check for refrains
                first_line = self.stanzas[0][0].strip().lower()
                third_line = self.stanzas[0][2].strip().lower()
                refrain_hits = 0
                for s in self.stanzas[1:5]:
                    if s[-1].strip().lower() in (first_line, third_line):
                        refrain_hits += 1
                if refrain_hits >= 3:
                    detected_forms.append('Villanelle')
                    confidence_scores['villanelle'] = 0.9
                else:
                    detected_forms.append('Possible villanelle (tercet/quatrain structure)')
                    confidence_scores['villanelle'] = 0.5

        # --- SESTINA (39 lines: 6 sixains + 3-line envoy) ---
        if total_lines in range(38, 41) and stanza_count == 7:
            sixain_check = all(l == 6 for l in stanza_lengths[:6])
            envoy_check = stanza_lengths[6] == 3
            if sixain_check and envoy_check:
                # Check for end-word rotation
                end_words = [[line.split()[-1].lower().rstrip('.,;:!?')
                              for line in s] for s in self.stanzas[:6]]
                if len(set(end_words[0])) == 6:
                    detected_forms.append('Sestina')
                    confidence_scores['sestina'] = 0.85

        # --- GHAZAL (autonomous couplets, shared refrain) ---
        if stanza_count >= 5 and all(l == 2 for l in stanza_lengths):
            # Check for repeated end-word/refrain
            last_words = [s[-1].split()[-1].lower().rstrip('.,;:!?') for s in self.stanzas]
            if len(set(last_words)) <= 2:
                detected_forms.append('Ghazal (autonomous couplets with refrain)')
                confidence_scores['ghazal'] = 0.8

        # --- BALLAD STANZA (quatrains, alternating 4/3 stress) ---
        if all(l == 4 for l in stanza_lengths) and stanza_count >= 3:
            detected_forms.append('Ballad/hymn stanza (regular quatrains)')
            confidence_scores['ballad'] = 0.5

        # --- TERZA RIMA (tercets with interlocking rhyme) ---
        if all(l == 3 for l in stanza_lengths[:-1]) and stanza_count >= 4:
            detected_forms.append('Possible terza rima (tercet-based)')
            confidence_scores['terza_rima'] = 0.4

        # --- FREE VERSE ---
        if not detected_forms:
            detected_forms.append('Free verse / open form')
            confidence_scores['free_verse'] = 0.5

        best_form = max(confidence_scores, key=confidence_scores.get) if confidence_scores else 'free_verse'
        best_confidence = confidence_scores.get(best_form, 0)

        return {
            'score': round(best_confidence, 3),
            'method': 'Fixed Form Detection (Hollander/Foster)',
            'detected_forms': detected_forms,
            'confidence_scores': {k: round(v, 3) for k, v in confidence_scores.items()},
            'total_lines': total_lines,
            'stanza_count': stanza_count,
            'stanza_lengths': stanza_lengths,
            'best_match': best_form,
            'precedent': (
                "Hollander: Each form carries its own meaning — the sonnet's "
                "compression, the villanelle's obsessive circularity, the sestina's "
                "mathematical rotation. Foster: Recognizing the form activates "
                "the reader's awareness of how constraint shapes content."
            ),
            'interpretation': (
                f"Best form match: {detected_forms[0]} "
                f"(confidence: {best_confidence:.0%}). "
                f"{stanza_count} stanzas with lengths {stanza_lengths[:10]}."
            ),
        }

    def analyze_stanza_structure(self) -> dict:
        """
        METHOD: Stanza Analysis
        SOURCES: Pinsky (Singing School), Hollander (Rhyme's Reason)

        Analyze stanza regularity, variation, and line-count patterns.
        """
        if not self.stanzas:
            return {'score': 0, 'method': 'Stanza Analysis'}

        lengths = [len(s) for s in self.stanzas]
        length_counter = Counter(lengths)

        # Regularity: how uniform are stanza lengths?
        if len(set(lengths)) == 1:
            regularity = 1.0
            pattern = 'uniform'
        else:
            dominant = length_counter.most_common(1)[0]
            regularity = dominant[1] / len(lengths)
            pattern = 'mostly regular' if regularity > 0.7 else 'variable' if regularity > 0.4 else 'irregular'

        # Syllable counts per line within stanzas (for syllabic verse detection)
        syllabic_patterns = []
        for s in self.stanzas[:5]:
            stanza_syllables = []
            for line in s:
                words = [w for w in word_tokenize(line) if w.isalpha()]
                syl_count = sum(syllable_count(w) for w in words)
                stanza_syllables.append(syl_count)
            syllabic_patterns.append(stanza_syllables)

        # Check if syllabic pattern repeats across stanzas
        syllabic_verse = False
        if len(syllabic_patterns) >= 2:
            first_pattern = syllabic_patterns[0]
            matches = sum(1 for sp in syllabic_patterns[1:]
                          if len(sp) == len(first_pattern)
                          and all(abs(a - b) <= 1 for a, b in zip(sp, first_pattern)))
            if matches >= len(syllabic_patterns) // 2:
                syllabic_verse = True

        # Custom form detection (Pinsky: Hardy/Herbert make new forms for each poem)
        stanza_name_map = {
            2: 'couplet', 3: 'tercet', 4: 'quatrain', 5: 'quintain',
            6: 'sixain/sestet', 7: 'septet', 8: 'octave', 9: 'Spenserian stanza',
        }
        dominant_stanza = length_counter.most_common(1)[0][0]
        stanza_name = stanza_name_map.get(dominant_stanza, f'{dominant_stanza}-line stanza')

        score = min(1.0, regularity * 0.5 + (1 if syllabic_verse else 0) * 0.3
                    + (0.2 if len(self.stanzas) > 3 else 0))

        return {
            'score': round(score, 3),
            'method': 'Stanza Analysis (Pinsky/Hollander)',
            'stanza_count': len(self.stanzas),
            'stanza_lengths': lengths,
            'dominant_stanza_type': stanza_name,
            'regularity': round(regularity, 3),
            'pattern': pattern,
            'syllabic_verse_detected': syllabic_verse,
            'syllabic_patterns': syllabic_patterns[:3],
            'precedent': (
                "Pinsky: Hardy and Herbert make a new form for each poem. "
                "Hollander: Stanza length carries meaning — couplets close, "
                "quatrains balance, tercets drive forward."
            ),
            'interpretation': (
                f"{pattern.capitalize()} stanza structure: {len(self.stanzas)} "
                f"{stanza_name}s (regularity {regularity:.0%}). "
                f"{'Syllabic verse pattern detected.' if syllabic_verse else ''}"
            ),
        }

    def analyze_volta(self) -> dict:
        """
        METHOD: Volta / Turn Detection
        SOURCES: Hollander (Rhyme's Reason), Foster (How to Read Poetry),
                 Ciardi (How Does a Poem Mean)

        Detect argumentative, tonal, or thematic shifts within the text.
        """
        turn_markers = {
            'but', 'yet', 'however', 'nevertheless', 'still', 'though',
            'although', 'whereas', 'instead', 'rather', 'except',
            'and yet', 'but yet', 'even so', 'on the other hand',
        }
        intensifiers = {
            'now', 'then', 'so', 'thus', 'therefore', 'hence', 'indeed',
            'truly', 'ah', 'oh', 'o', 'alas', 'behold', 'lo', 'hark',
        }

        turns = []
        for i, line in enumerate(self.lines):
            words = [w.lower() for w in word_tokenize(line)]
            # Check if line starts with a turn marker
            first_words = ' '.join(words[:3])
            for marker in turn_markers:
                if first_words.startswith(marker):
                    position_ratio = i / max(len(self.lines) - 1, 1)
                    turns.append({
                        'line_number': i + 1,
                        'line': line.strip()[:80],
                        'marker': marker,
                        'type': 'adversative',
                        'position': round(position_ratio, 3),
                    })
                    break
            # Check for exclamatory/intensifying turns
            for marker in intensifiers:
                if words and words[0] == marker:
                    position_ratio = i / max(len(self.lines) - 1, 1)
                    turns.append({
                        'line_number': i + 1,
                        'line': line.strip()[:80],
                        'marker': marker,
                        'type': 'intensifying',
                        'position': round(position_ratio, 3),
                    })
                    break

        # Check for structural volta at sonnet turn points
        structural_turns = []
        if len(self.lines) == 14:
            # Petrarchan volta at line 9
            if any(t['line_number'] == 9 for t in turns):
                structural_turns.append('Petrarchan volta at line 9')
            # Shakespearean volta at line 13 (couplet)
            if any(t['line_number'] == 13 for t in turns):
                structural_turns.append('Shakespearean couplet turn at line 13')

        adversative = [t for t in turns if t['type'] == 'adversative']
        score = min(1.0, len(adversative) * 0.15 + len(structural_turns) * 0.3)

        return {
            'score': round(score, 3),
            'method': 'Volta / Turn Detection (Hollander/Foster/Ciardi)',
            'turns': turns[:15],
            'adversative_turns': len(adversative),
            'intensifying_turns': len([t for t in turns if t['type'] == 'intensifying']),
            'structural_turns': structural_turns,
            'precedent': (
                "Hollander: The sonnet's volta is where the argument pivots. "
                "Foster: The turn signals the poem's deeper move — from observation "
                "to insight, from problem to response, from question to answer."
            ),
            'interpretation': (
                f"{len(adversative)} adversative turns ('but', 'yet', etc.) and "
                f"{len([t for t in turns if t['type'] == 'intensifying'])} intensifying turns detected. "
                f"{'; '.join(structural_turns) if structural_turns else 'No structural volta at standard positions.'}."
            ),
        }

    def analyze_refrain(self) -> dict:
        """
        METHOD: Refrain & Repetition Tracking
        SOURCES: Pinsky (Singing School), Hollander (Rhyme's Reason)

        Track recurring lines, anaphora, and refrain patterns.
        """
        # Exact line repetition
        line_normalized = [line.strip().lower() for line in self.lines if line.strip()]
        line_counts = Counter(line_normalized)
        repeated_lines = {line: count for line, count in line_counts.items() if count > 1}

        # Anaphora: repeated line openings
        first_words = [line.split()[0].lower() if line.split() else '' for line in line_normalized]
        first_word_counts = Counter(first_words)
        anaphora_words = {w: c for w, c in first_word_counts.items() if c >= 3 and w}

        # Two-word anaphora
        first_two = [' '.join(line.split()[:2]).lower() for line in line_normalized if len(line.split()) >= 2]
        two_word_counts = Counter(first_two)
        anaphora_phrases = {p: c for p, c in two_word_counts.items() if c >= 2}

        # Epistrophe: repeated line endings
        last_words = [line.split()[-1].lower().rstrip('.,;:!?') if line.split() else '' for line in line_normalized]
        last_word_counts = Counter(last_words)
        epistrophe_words = {w: c for w, c in last_word_counts.items() if c >= 3 and w}

        refrain_count = len(repeated_lines)
        anaphora_count = len(anaphora_words)

        score = min(1.0, refrain_count * 0.2 + anaphora_count * 0.15
                    + len(anaphora_phrases) * 0.1 + len(epistrophe_words) * 0.1)

        return {
            'score': round(score, 3),
            'method': 'Refrain & Repetition Tracking (Pinsky/Hollander)',
            'repeated_lines': {k: v for k, v in sorted(repeated_lines.items(),
                              key=lambda x: -x[1])[:10]},
            'anaphora_words': dict(sorted(anaphora_words.items(), key=lambda x: -x[1])[:10]),
            'anaphora_phrases': dict(sorted(anaphora_phrases.items(), key=lambda x: -x[1])[:10]),
            'epistrophe_words': dict(sorted(epistrophe_words.items(), key=lambda x: -x[1])[:10]),
            'refrain_count': refrain_count,
            'anaphora_count': anaphora_count,
            'precedent': (
                "Pinsky: Anaphora creates incantatory power; refrains are 'knit "
                "into' the poem, gaining new meaning each time they recur. "
                "Hollander: The villanelle's refrains accumulate emotional weight "
                "through repetition in changing contexts."
            ),
            'interpretation': (
                f"{refrain_count} repeated line(s), {anaphora_count} anaphoric patterns, "
                f"{len(epistrophe_words)} epistrophic patterns. "
                f"{'Strong repetitive/ritualistic texture.' if score > 0.5 else 'Some repetitive patterning.' if score > 0.2 else 'Minimal repetitive structure.'}"
            ),
        }

    def analyze_line_length(self) -> dict:
        """
        METHOD: Line-Length Patterning
        SOURCES: Pinsky (Singing School), Ciardi (How Does a Poem Mean)

        Analyze syllable and word count variation across lines.
        """
        if not self.lines:
            return {'score': 0, 'method': 'Line-Length Patterning'}

        line_data = []
        for line in self.lines:
            words = [w for w in word_tokenize(line) if w.isalpha()]
            syl_count = sum(syllable_count(w) for w in words)
            line_data.append({
                'word_count': len(words),
                'syllable_count': syl_count,
            })

        syl_counts = [d['syllable_count'] for d in line_data]
        word_counts = [d['word_count'] for d in line_data]

        avg_syllables = sum(syl_counts) / max(len(syl_counts), 1)
        syl_variance = sum((s - avg_syllables) ** 2 for s in syl_counts) / max(len(syl_counts), 1)
        syl_std = math.sqrt(syl_variance)

        # Coefficient of variation: lower = more regular
        cv = syl_std / max(avg_syllables, 1)
        regularity = max(0, 1 - cv)

        # Detect monosyllable-dominant vs polysyllable-dominant passages (Pinsky)
        all_words = [w for w in self.words if w.isalpha()]
        mono_ratio = sum(1 for w in all_words if syllable_count(w) == 1) / max(len(all_words), 1)

        score = min(1.0, regularity * 0.5 + abs(mono_ratio - 0.5) * 1.5)

        return {
            'score': round(score, 3),
            'method': 'Line-Length Patterning (Pinsky/Ciardi)',
            'average_syllables_per_line': round(avg_syllables, 2),
            'syllable_std_dev': round(syl_std, 2),
            'line_length_regularity': round(regularity, 3),
            'monosyllable_ratio': round(mono_ratio, 3),
            'shortest_line_syllables': min(syl_counts) if syl_counts else 0,
            'longest_line_syllables': max(syl_counts) if syl_counts else 0,
            'precedent': (
                "Pinsky: Polysyllabic passages dance; monosyllabic passages "
                "plod with weight. Ciardi: Line length is a non-metrical "
                "accelerating or impeding device."
            ),
            'interpretation': (
                f"Average {avg_syllables:.1f} syllables/line (σ={syl_std:.1f}). "
                f"{'Very regular' if regularity > 0.8 else 'Moderately regular' if regularity > 0.5 else 'Variable'} "
                f"line lengths. {mono_ratio:.0%} monosyllabic words "
                f"({'heavy/emphatic' if mono_ratio > 0.65 else 'balanced' if mono_ratio > 0.45 else 'fluid/polysyllabic'} texture)."
            ),
        }

    def analyze_closure(self) -> dict:
        """
        METHOD: Closure Analysis
        SOURCES: Ciardi (How Does a Poem Mean), Foster (How to Read Literature)

        Analyze how the text ends relative to how it begins.
        """
        if len(self.lines) < 4:
            return {'score': 0, 'method': 'Closure Analysis'}

        opening = ' '.join(self.lines[:3])
        closing = ' '.join(self.lines[-3:])

        open_words = set(w.lower() for w in word_tokenize(opening) if w.isalpha())
        close_words = set(w.lower() for w in word_tokenize(closing) if w.isalpha())

        # Lexical overlap (circularity)
        overlap = open_words & close_words
        overlap_ratio = len(overlap) / max(len(open_words | close_words), 1)

        # Check for exact or near-exact line repetition (frame structure)
        first_line = self.lines[0].strip().lower()
        last_line = self.lines[-1].strip().lower()
        frame = first_line == last_line
        near_frame = (not frame and len(set(first_line.split()) & set(last_line.split()))
                      / max(len(set(first_line.split())), 1) > 0.5)

        # Terminal punctuation (definitive vs. open ending)
        last_char = self.lines[-1].strip()[-1] if self.lines[-1].strip() else ''
        if last_char == '.':
            ending_type = 'definitive (period)'
        elif last_char == '?':
            ending_type = 'interrogative (question)'
        elif last_char == '!':
            ending_type = 'exclamatory'
        elif last_char == '—' or last_char == '-':
            ending_type = 'interrupted (dash)'
        elif last_char == '…' or self.lines[-1].strip().endswith('...'):
            ending_type = 'trailing (ellipsis)'
        else:
            ending_type = 'open (no terminal punctuation)'

        score = min(1.0, overlap_ratio * 2 + (0.3 if frame else 0.15 if near_frame else 0))

        return {
            'score': round(score, 3),
            'method': 'Closure Analysis (Ciardi/Foster)',
            'lexical_overlap': round(overlap_ratio, 3),
            'shared_vocabulary': list(overlap)[:20],
            'frame_structure': frame,
            'near_frame': near_frame,
            'ending_type': ending_type,
            'first_line': self.lines[0].strip()[:80],
            'last_line': self.lines[-1].strip()[:80],
            'precedent': (
                "Ciardi: Closure may be circular (returning to the beginning), "
                "progressive (arriving somewhere new), or irresolutive (refusing "
                "to close). Foster: How a work ends reveals what it's really about."
            ),
            'interpretation': (
                f"Ending type: {ending_type}. "
                f"{'Frame structure (first = last line).' if frame else 'Near-frame (shared vocabulary).' if near_frame else ''} "
                f"Lexical overlap between opening and closing: {overlap_ratio:.0%}."
            ),
        }

    # ==================================================================
    # III. FIGURATIVE LANGUAGE
    # ==================================================================

    def analyze_metaphor_simile(self) -> dict:
        """
        METHOD: Metaphor & Simile Detection
        SOURCES: Ciardi (How Does a Poem Mean), Foster (How to Read Poetry/Literature)

        Identify figurative comparisons: explicit (simile) and implicit (metaphor).
        """
        simile_patterns = [
            r'\blike\s+(?:a|an|the)\b',
            r'\bas\s+\w+\s+as\b',
            r'\bas\s+if\b',
            r'\bas\s+though\b',
            r'\bresembl\w+\b',
        ]

        metaphor_indicators = {
            'is', 'was', 'were', 'are', 'am', 'been', 'become', 'becomes',
            'became', 'turned', 'transformed', 'grew',
        }

        # Scan for similes
        similes = []
        for i, sent in enumerate(self.sentences):
            for pattern in simile_patterns:
                matches = re.finditer(pattern, sent, re.IGNORECASE)
                for m in matches:
                    context_start = max(0, m.start() - 40)
                    context_end = min(len(sent), m.end() + 40)
                    similes.append({
                        'sentence': i + 1,
                        'marker': m.group(),
                        'context': sent[context_start:context_end].strip(),
                    })

        # Scan for potential metaphors (X is Y where Y is concrete/imagistic)
        concrete_nouns = {
            'fire', 'flame', 'ice', 'stone', 'river', 'ocean', 'sea',
            'mountain', 'tree', 'bird', 'snake', 'wolf', 'lion', 'rose',
            'storm', 'star', 'sun', 'moon', 'shadow', 'mirror', 'sword',
            'crown', 'chain', 'cage', 'bridge', 'door', 'window', 'wall',
            'garden', 'desert', 'forest', 'island', 'ship', 'road',
            'light', 'darkness', 'gold', 'silver', 'blood', 'bone',
        }

        metaphors = []
        for i, sent in enumerate(self.sentences):
            words = word_tokenize(sent.lower())
            for j, w in enumerate(words):
                if w in metaphor_indicators and j > 0 and j < len(words) - 1:
                    next_words = set(words[j + 1:j + 4])
                    if next_words & concrete_nouns:
                        metaphors.append({
                            'sentence': i + 1,
                            'indicator': w,
                            'context': sent[:150].strip(),
                        })

        total_sents = max(len(self.sentences), 1)
        simile_density = len(similes) / total_sents
        metaphor_density = len(metaphors) / total_sents
        figurative_density = (len(similes) + len(metaphors)) / total_sents

        score = min(1.0, figurative_density * 3)

        return {
            'score': round(score, 3),
            'method': 'Metaphor & Simile Detection (Ciardi/Foster)',
            'simile_count': len(similes),
            'metaphor_count': len(metaphors),
            'simile_density': round(simile_density, 4),
            'metaphor_density': round(metaphor_density, 4),
            'figurative_density': round(figurative_density, 4),
            'similes': similes[:10],
            'metaphors': metaphors[:10],
            'precedent': (
                "Ciardi: The metaphoric contract — X (unknown) = Y (known) — is "
                "the fundamental operation of poetry. Foster: Similes are explicit "
                "('like'), metaphors implicit; both deflect literal meaning toward "
                "a secondary, enriched meaning."
            ),
            'interpretation': (
                f"{len(similes)} similes, {len(metaphors)} potential metaphors. "
                f"Figurative density: {figurative_density:.0%} of sentences. "
                f"{'Richly figurative' if figurative_density > 0.3 else 'Moderately figurative' if figurative_density > 0.1 else 'Predominantly literal'}."
            ),
        }

    def analyze_image_clustering(self) -> dict:
        """
        METHOD: Image Clustering
        SOURCES: Ciardi (How Does a Poem Mean), Foster (How to Read Literature)

        Group recurring sensory images by domain and track their development.
        """
        image_domains = {
            'visual_light': {
                'light', 'dark', 'shadow', 'bright', 'dim', 'glow', 'gleam',
                'shine', 'glitter', 'flash', 'spark', 'flame', 'blaze',
                'radiant', 'luminous', 'pale', 'black', 'white', 'red',
                'blue', 'green', 'gold', 'silver', 'color', 'colour',
            },
            'auditory': {
                'sound', 'noise', 'silence', 'quiet', 'loud', 'soft',
                'whisper', 'shout', 'cry', 'sing', 'song', 'music',
                'voice', 'echo', 'ring', 'chime', 'toll', 'bell',
                'thunder', 'murmur', 'hum', 'buzz', 'roar',
            },
            'tactile': {
                'touch', 'feel', 'cold', 'warm', 'hot', 'cool', 'smooth',
                'rough', 'soft', 'hard', 'sharp', 'dull', 'wet', 'dry',
                'heavy', 'light', 'tender', 'harsh', 'gentle', 'sting',
            },
            'kinesthetic': {
                'move', 'run', 'walk', 'fall', 'rise', 'climb', 'fly',
                'float', 'sink', 'dance', 'leap', 'crawl', 'stretch',
                'bend', 'turn', 'spin', 'tremble', 'shake', 'flow',
            },
            'natural': {
                'tree', 'flower', 'leaf', 'grass', 'river', 'ocean', 'sea',
                'mountain', 'valley', 'forest', 'field', 'sky', 'cloud',
                'wind', 'rain', 'snow', 'sun', 'moon', 'star', 'earth',
                'stone', 'rock', 'bird', 'fish', 'animal', 'root', 'seed',
            },
            'bodily': {
                'blood', 'bone', 'flesh', 'skin', 'heart', 'eye', 'hand',
                'mouth', 'tongue', 'breath', 'face', 'head', 'foot',
                'body', 'hair', 'finger', 'lip', 'tear', 'sweat',
            },
            'domestic': {
                'house', 'home', 'room', 'door', 'window', 'wall', 'floor',
                'roof', 'bed', 'table', 'chair', 'fire', 'hearth', 'lamp',
                'candle', 'glass', 'cup', 'plate', 'bread', 'garden',
            },
        }

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)

        domain_hits = {}
        for domain, vocab in image_domains.items():
            hits = sum(1 for w in all_words if w in vocab)
            domain_hits[domain] = {
                'count': hits,
                'density': round(hits / total, 5),
            }

        # Sort by density
        ranked = sorted(domain_hits.items(), key=lambda x: -x[1]['density'])
        dominant_domain = ranked[0][0] if ranked else 'none'

        # Image diversity: how many domains are active?
        active_domains = sum(1 for d in domain_hits.values() if d['density'] > 0.005)

        total_imagery = sum(d['count'] for d in domain_hits.values())
        imagery_density = total_imagery / total

        score = min(1.0, imagery_density * 5 + active_domains * 0.05)

        return {
            'score': round(score, 3),
            'method': 'Image Clustering (Ciardi/Foster)',
            'domain_analysis': {k: v for k, v in ranked},
            'dominant_domain': dominant_domain,
            'active_domains': active_domains,
            'total_image_words': total_imagery,
            'imagery_density': round(imagery_density, 4),
            'precedent': (
                "Ciardi: A poet's image patterns reveal their consciousness — "
                "the categories arise naturally from the poet's mind, not imposed "
                "from outside. Foster: Recurring images create thematic clusters "
                "that function like musical motifs."
            ),
            'interpretation': (
                f"Dominant image domain: {dominant_domain} "
                f"({domain_hits[dominant_domain]['density']:.1%}). "
                f"{active_domains} of {len(image_domains)} domains active. "
                f"Overall imagery density: {imagery_density:.1%}."
            ),
        }

    def analyze_concrete_abstract(self) -> dict:
        """
        METHOD: Concrete vs. Abstract Ratio
        SOURCES: Ciardi (How Does a Poem Mean), Foster (How to Read Poetry)

        Measure the balance between specific/sensory and general/abstract vocabulary.
        """
        tagged = pos_tag(self.words)

        # Concrete: nouns that are tangible, specific
        concrete_markers = {
            'NN', 'NNS',  # common nouns (approximate: many are concrete)
        }
        abstract_markers = {
            'JJ', 'JJR', 'JJS',  # adjectives (often abstract)
        }

        # Use POS + vocabulary check
        abstract_vocab = {
            'truth', 'beauty', 'justice', 'freedom', 'love', 'hope', 'faith',
            'virtue', 'wisdom', 'knowledge', 'power', 'time', 'eternity',
            'spirit', 'soul', 'mind', 'thought', 'idea', 'meaning',
            'reason', 'nature', 'reality', 'existence', 'being', 'nothing',
            'death', 'life', 'peace', 'war', 'truth', 'honor', 'glory',
            'shame', 'grief', 'sorrow', 'joy', 'happiness', 'despair',
            'absence', 'presence', 'silence', 'memory', 'desire', 'fear',
        }

        concrete_vocab = {
            'stone', 'river', 'tree', 'hand', 'eye', 'blood', 'bone',
            'bread', 'wine', 'water', 'fire', 'earth', 'sun', 'moon',
            'star', 'bird', 'fish', 'horse', 'dog', 'cat', 'flower',
            'leaf', 'grass', 'rain', 'snow', 'wind', 'iron', 'gold',
            'silver', 'glass', 'wood', 'house', 'door', 'window', 'bed',
            'table', 'chair', 'knife', 'sword', 'ship', 'road', 'bridge',
        }

        concrete_count = sum(1 for w in self.words if w.lower() in concrete_vocab)
        abstract_count = sum(1 for w in self.words if w.lower() in abstract_vocab)
        total = max(concrete_count + abstract_count, 1)

        concrete_ratio = concrete_count / total
        abstract_ratio = abstract_count / total

        # Vocabulary specificity (Ciardi: specific naming vs. general)
        all_nouns = [w.lower() for w, t in tagged if t in ('NN', 'NNS', 'NNP', 'NNPS')]
        unique_nouns = len(set(all_nouns))
        noun_specificity = unique_nouns / max(len(all_nouns), 1)

        if concrete_ratio > 0.6:
            texture = 'concrete/imagistic'
        elif abstract_ratio > 0.6:
            texture = 'abstract/philosophical'
        else:
            texture = 'balanced'

        score = min(1.0, abs(concrete_ratio - abstract_ratio) * 2 + noun_specificity * 0.3)

        return {
            'score': round(score, 3),
            'method': 'Concrete vs. Abstract Ratio (Ciardi/Foster)',
            'concrete_count': concrete_count,
            'abstract_count': abstract_count,
            'concrete_ratio': round(concrete_ratio, 3),
            'abstract_ratio': round(abstract_ratio, 3),
            'texture': texture,
            'noun_specificity': round(noun_specificity, 3),
            'total_unique_nouns': unique_nouns,
            'precedent': (
                "Ciardi: Specific names (orchis, hyacinth) anchor abstraction. "
                "Foster: Concrete details ground fantastical content — 'imaginary "
                "gardens with real toads' (Moore)."
            ),
            'interpretation': (
                f"Diction texture: {texture}. "
                f"Concrete: {concrete_ratio:.0%}, Abstract: {abstract_ratio:.0%}. "
                f"Noun specificity: {noun_specificity:.0%} unique nouns."
            ),
        }

    def analyze_symbol_markers(self) -> dict:
        """
        METHOD: Symbol & Allegory Markers
        SOURCES: Foster (How to Read Literature Like a Professor),
                 Ciardi (How Does a Poem Mean)

        Detect objects and actions that carry layered symbolic meaning.
        """
        # Foster's core symbol clusters
        symbol_domains = {
            'journey_quest': QUEST_VOCAB,
            'communion_meal': COMMUNION_VOCAB,
            'water_baptism': {
                'water', 'river', 'sea', 'ocean', 'lake', 'pool', 'fountain',
                'spring', 'stream', 'flood', 'drown', 'swim', 'baptize',
                'wash', 'cleanse', 'dive', 'submerge', 'emerge', 'shore',
            },
            'garden_nature': {
                'garden', 'eden', 'paradise', 'flower', 'rose', 'lily',
                'apple', 'fruit', 'tree', 'vine', 'thorn', 'serpent',
                'innocent', 'fall', 'cultivate', 'bloom', 'wither',
            },
            'blindness_sight': {
                'blind', 'see', 'sight', 'vision', 'eye', 'look', 'gaze',
                'watch', 'observe', 'dark', 'light', 'illuminate', 'reveal',
                'hide', 'conceal', 'veil', 'mask', 'transparent', 'opaque',
            },
            'flight_freedom': {
                'fly', 'flight', 'wing', 'bird', 'soar', 'cage', 'free',
                'freedom', 'escape', 'prison', 'chain', 'bound', 'release',
                'sky', 'heaven', 'fall', 'icarus', 'eagle', 'dove',
            },
        }

        all_words = set(w.lower() for w in self.words if w.isalpha())
        total_words = max(len([w for w in self.words if w.isalpha()]), 1)

        domain_results = {}
        total_symbol_hits = 0
        for domain, vocab in symbol_domains.items():
            hits = all_words & vocab
            count = sum(1 for w in self.words if w.lower() in vocab)
            domain_results[domain] = {
                'unique_terms': list(hits)[:10],
                'count': count,
                'density': round(count / total_words, 5),
            }
            total_symbol_hits += count

        active = sum(1 for d in domain_results.values() if d['density'] > 0.002)
        symbol_density = total_symbol_hits / total_words

        score = min(1.0, symbol_density * 8 + active * 0.05)

        return {
            'score': round(score, 3),
            'method': 'Symbol & Allegory Markers (Foster/Ciardi)',
            'domain_results': domain_results,
            'total_symbol_hits': total_symbol_hits,
            'symbol_density': round(symbol_density, 4),
            'active_symbol_domains': active,
            'precedent': (
                "Foster: Symbols carry multiple, simultaneous meanings — unlike "
                "allegory's one-to-one mapping. A journey is always also a quest. "
                "Eating is always also communion. Submersion is always also baptism."
            ),
            'interpretation': (
                f"{active} symbolic domains active. "
                f"Total symbolic vocabulary density: {symbol_density:.1%}. "
                f"Dominant: {max(domain_results, key=lambda k: domain_results[k]['density'])}."
            ),
        }

    # ==================================================================
    # IV. DICTION & VOCABULARY
    # ==================================================================

    def analyze_etymology_register(self) -> dict:
        """
        METHOD: Anglo-Saxon vs. Latinate Ratio
        SOURCES: Foster (How to Read Poetry), Pinsky (Singing School)

        Detect the etymological register of vocabulary.
        Anglo-Saxon = plain, blunt, embodied. Latinate = formal, abstract, learned.
        """
        all_words = [w.lower() for w in self.words if w.isalpha() and len(w) > 3]
        total = max(len(all_words), 1)

        latinate_count = 0
        anglo_count = 0

        for w in all_words:
            if w in ANGLO_SAXON_CORE:
                anglo_count += 1
            elif any(w.endswith(s) for s in LATINATE_SUFFIXES):
                latinate_count += 1
            elif any(w.endswith(s) for s in ANGLO_SAXON_SUFFIXES):
                anglo_count += 1

        classified = max(latinate_count + anglo_count, 1)
        latinate_ratio = latinate_count / classified
        anglo_ratio = anglo_count / classified

        if latinate_ratio > 0.6:
            register = 'Latinate/formal/learned'
        elif anglo_ratio > 0.6:
            register = 'Anglo-Saxon/plain/embodied'
        else:
            register = 'Mixed register'

        score = min(1.0, abs(latinate_ratio - anglo_ratio) + 0.2)

        return {
            'score': round(score, 3),
            'method': 'Anglo-Saxon vs. Latinate Ratio (Foster/Pinsky)',
            'latinate_count': latinate_count,
            'anglo_saxon_count': anglo_count,
            'latinate_ratio': round(latinate_ratio, 3),
            'anglo_saxon_ratio': round(anglo_ratio, 3),
            'dominant_register': register,
            'precedent': (
                "Foster: Anglo-Saxon words are short, blunt, physical; Latinate "
                "words are longer, more abstract, more 'official.' The mixture "
                "carries class and educational implications."
            ),
            'interpretation': (
                f"Dominant etymological register: {register}. "
                f"Latinate: {latinate_ratio:.0%}, Anglo-Saxon: {anglo_ratio:.0%}."
            ),
        }

    def analyze_vocabulary_richness(self) -> dict:
        """
        METHOD: Vocabulary Richness
        SOURCES: Ciardi (How Does a Poem Mean), Pinsky (Singing School)

        Type-token ratio, hapax legomena, and vocabulary diversity.
        """
        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)
        unique = set(all_words)
        ttr = len(unique) / total

        # Hapax legomena
        word_counts = Counter(all_words)
        hapax = [w for w, c in word_counts.items() if c == 1]
        hapax_ratio = len(hapax) / total

        # Dis legomena (words used exactly twice)
        dis = [w for w, c in word_counts.items() if c == 2]

        score = min(1.0, ttr * 0.8 + hapax_ratio * 0.5)

        return {
            'score': round(score, 3),
            'method': 'Vocabulary Richness (Ciardi/Pinsky)',
            'type_token_ratio': round(ttr, 4),
            'unique_words': len(unique),
            'total_words': total,
            'hapax_count': len(hapax),
            'hapax_ratio': round(hapax_ratio, 4),
            'dis_legomena_count': len(dis),
            'top_repeated_words': dict(word_counts.most_common(15)),
            'precedent': (
                "Ciardi: Vocabulary specificity reveals the poet's precision — "
                "specific naming vs. general categories. Pinsky: Word choice "
                "carries the 'feel and aroma' of meaning."
            ),
            'interpretation': (
                f"Type-token ratio: {ttr:.3f} "
                f"({'rich' if ttr > 0.7 else 'moderate' if ttr > 0.5 else 'repetitive'} vocabulary). "
                f"{len(hapax)} hapax legomena ({hapax_ratio:.0%} of words used only once)."
            ),
        }

    def analyze_register_mixing(self) -> dict:
        """
        METHOD: Register Mixing Detection
        SOURCES: Pinsky (Singing School), Foster (How to Read Poetry)

        Detect shifts between formal, colloquial, archaic, and technical registers.
        """
        formal_vocab = {
            'therefore', 'moreover', 'whereas', 'wherein', 'nevertheless',
            'notwithstanding', 'hitherto', 'heretofore', 'aforementioned',
            'thus', 'hence', 'accordingly', 'manifestly', 'verily',
            'thou', 'thee', 'thy', 'thine', 'hath', 'doth', 'shalt',
            'whence', 'whither', 'forsooth', 'methinks', 'prithee',
            'ere', 'whilst', 'amongst', 'betwixt', 'nigh', 'aught',
        }
        colloquial_vocab = {
            'yeah', 'nah', 'gonna', 'wanna', 'gotta', 'kinda', 'sorta',
            'hey', 'yo', 'dude', 'man', 'like', 'totally', 'whatever',
            'stuff', 'thing', 'okay', 'ok', 'cool', 'awesome', 'damn',
            'hell', 'shit', 'fuck', 'crap', 'ain\'t', 'y\'all',
        }
        technical_vocab = {
            'algorithm', 'quantum', 'molecule', 'photon', 'genome',
            'theorem', 'hypothesis', 'paradigm', 'dialectic', 'ontology',
            'epistemology', 'hermeneutic', 'phenomenology', 'syntax',
            'morpheme', 'phoneme', 'isotope', 'entropy', 'catalyst',
        }

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)

        formal_hits = sum(1 for w in all_words if w in formal_vocab)
        colloquial_hits = sum(1 for w in all_words if w in colloquial_vocab)
        technical_hits = sum(1 for w in all_words if w in technical_vocab)

        # Register diversity score
        active_registers = sum(1 for h in [formal_hits, colloquial_hits, technical_hits] if h > 0)
        mixing = active_registers >= 2

        score = min(1.0, (formal_hits + colloquial_hits + technical_hits) / total * 10
                    + (0.3 if mixing else 0))

        return {
            'score': round(score, 3),
            'method': 'Register Mixing Detection (Pinsky/Foster)',
            'formal_count': formal_hits,
            'colloquial_count': colloquial_hits,
            'technical_count': technical_hits,
            'register_mixing': mixing,
            'active_registers': active_registers,
            'precedent': (
                "Pinsky: Sterling Brown transforms ethnic slurs into 'lush texture'; "
                "sacred mixed with profane creates power. Foster: Register shifts "
                "signal social comment, irony, or defamiliarization."
            ),
            'interpretation': (
                f"{'Register mixing detected' if mixing else 'Relatively uniform register'}. "
                f"Formal: {formal_hits}, Colloquial: {colloquial_hits}, "
                f"Technical: {technical_hits}."
            ),
        }

    def analyze_pos_profile(self) -> dict:
        """
        METHOD: Parts of Speech Profile
        SOURCES: Foster (How to Read Poetry), Ciardi (How Does a Poem Mean)

        Analyze noun/verb/adjective/adverb distributions and unusual POS usage.
        """
        tagged = pos_tag(self.words)
        pos_counts = Counter(tag for _, tag in tagged)
        total = max(sum(pos_counts.values()), 1)

        # Group into major categories
        nouns = sum(pos_counts.get(t, 0) for t in ('NN', 'NNS', 'NNP', 'NNPS'))
        verbs = sum(pos_counts.get(t, 0) for t in ('VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ'))
        adjectives = sum(pos_counts.get(t, 0) for t in ('JJ', 'JJR', 'JJS'))
        adverbs = sum(pos_counts.get(t, 0) for t in ('RB', 'RBR', 'RBS'))
        pronouns = sum(pos_counts.get(t, 0) for t in ('PRP', 'PRP$', 'WP', 'WP$'))

        noun_ratio = nouns / total
        verb_ratio = verbs / total
        adj_ratio = adjectives / total
        adv_ratio = adverbs / total

        # Determine style tendency
        if noun_ratio > verb_ratio * 1.5:
            style = 'noun-heavy (descriptive/static)'
        elif verb_ratio > noun_ratio * 1.2:
            style = 'verb-heavy (active/dynamic)'
        elif adj_ratio > 0.12:
            style = 'adjective-rich (ornamental/sensory)'
        else:
            style = 'balanced'

        score = min(1.0, abs(noun_ratio - verb_ratio) * 3 + adj_ratio * 2)

        return {
            'score': round(score, 3),
            'method': 'Parts of Speech Profile (Foster/Ciardi)',
            'noun_ratio': round(noun_ratio, 3),
            'verb_ratio': round(verb_ratio, 3),
            'adjective_ratio': round(adj_ratio, 3),
            'adverb_ratio': round(adv_ratio, 3),
            'pronoun_count': pronouns,
            'style_tendency': style,
            'pos_distribution': dict(pos_counts.most_common(10)),
            'precedent': (
                "Foster: Parts of speech tell you what the poem is DOING — "
                "nouns describe, verbs move, adjectives qualify. Ciardi: "
                "The ratio reveals whether the poem is static or dynamic."
            ),
            'interpretation': (
                f"Style: {style}. Nouns {noun_ratio:.0%}, Verbs {verb_ratio:.0%}, "
                f"Adjectives {adj_ratio:.0%}, Adverbs {adv_ratio:.0%}."
            ),
        }

    # ==================================================================
    # V. NARRATIVE & INTERTEXTUAL
    # ==================================================================

    def analyze_archetype(self) -> dict:
        """
        METHOD: Archetype / Quest Pattern Detection
        SOURCES: Foster (How to Read Literature Like a Professor)

        Detect mythic narrative patterns: quest, communion, sacrifice, rebirth.
        """
        all_words_lower = set(w.lower() for w in self.words if w.isalpha())
        total = max(len([w for w in self.words if w.isalpha()]), 1)

        archetypes = {
            'quest': QUEST_VOCAB,
            'communion': COMMUNION_VOCAB,
            'sacrifice': {
                'sacrifice', 'offering', 'altar', 'blood', 'lamb', 'cross',
                'crucify', 'martyr', 'victim', 'scapegoat', 'atonement',
                'redeem', 'die', 'death', 'suffer', 'wound', 'scar',
            },
            'rebirth': {
                'rebirth', 'resurrect', 'resurrection', 'renew', 'renewal',
                'reborn', 'awaken', 'arise', 'spring', 'dawn', 'new',
                'begin', 'beginning', 'emerge', 'transform', 'metamorphosis',
                'phoenix', 'seed', 'sprout', 'bloom',
            },
            'descent': {
                'descend', 'descent', 'fall', 'below', 'beneath', 'under',
                'underground', 'underworld', 'deep', 'depth', 'abyss',
                'pit', 'cave', 'tomb', 'buried', 'sink', 'drown',
                'hell', 'hades', 'inferno', 'darkness',
            },
        }

        results = {}
        total_hits = 0
        for name, vocab in archetypes.items():
            hits = all_words_lower & vocab
            count = sum(1 for w in self.words if w.lower() in vocab)
            results[name] = {
                'terms_found': list(hits)[:10],
                'count': count,
                'density': round(count / total, 5),
            }
            total_hits += count

        active = sum(1 for r in results.values() if r['density'] > 0.002)
        dominant = max(results, key=lambda k: results[k]['density'])

        score = min(1.0, total_hits / total * 10 + active * 0.05)

        return {
            'score': round(score, 3),
            'method': 'Archetype / Quest Pattern (Foster)',
            'archetype_results': results,
            'dominant_archetype': dominant,
            'active_archetypes': active,
            'precedent': (
                "Foster: All quests are really about self-knowledge. All meals "
                "are communion. All submersion is baptism. All flight is freedom. "
                "These patterns are the deep grammar of narrative."
            ),
            'interpretation': (
                f"Dominant archetype: {dominant} "
                f"({results[dominant]['density']:.1%}). "
                f"{active} archetypal patterns active."
            ),
        }

    def analyze_allusion(self) -> dict:
        """
        METHOD: Biblical & Mythological Allusion
        SOURCES: Foster (How to Read Literature Like a Professor)

        Detect density of sacred and classical references.
        """
        all_words_lower = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words_lower), 1)

        biblical_hits = sum(1 for w in all_words_lower if w in BIBLICAL_VOCAB)
        mythological_hits = sum(1 for w in all_words_lower if w in MYTHOLOGICAL_VOCAB)

        biblical_density = biblical_hits / total
        mythological_density = mythological_hits / total
        allusion_density = (biblical_hits + mythological_hits) / total

        if biblical_density > mythological_density:
            dominant = 'biblical/Christian'
        elif mythological_density > biblical_density:
            dominant = 'classical/mythological'
        else:
            dominant = 'balanced'

        score = min(1.0, allusion_density * 15)

        return {
            'score': round(score, 3),
            'method': 'Biblical & Mythological Allusion (Foster)',
            'biblical_density': round(biblical_density, 5),
            'mythological_density': round(mythological_density, 5),
            'allusion_density': round(allusion_density, 5),
            'biblical_count': biblical_hits,
            'mythological_count': mythological_hits,
            'dominant_allusion_type': dominant,
            'precedent': (
                "Foster: Biblical and mythological allusions provide authority "
                "and depth. They are the shared cultural vocabulary that writers "
                "invoke to layer meaning. Modern/ironic use of biblical material "
                "is just as significant as sincere use."
            ),
            'interpretation': (
                f"Allusion type: {dominant}. "
                f"Biblical density: {biblical_density:.1%}, "
                f"Mythological: {mythological_density:.1%}."
            ),
        }

    def analyze_seasonal_weather(self) -> dict:
        """
        METHOD: Seasonal & Weather Symbolism
        SOURCES: Foster (How to Read Literature Like a Professor)

        Detect elemental symbolic patterns: seasons, weather, time of day.
        """
        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)

        season_results = {}
        for season, vocab in SEASONAL_ASSOCIATIONS.items():
            count = sum(1 for w in all_words if w in vocab)
            season_results[season] = {
                'count': count,
                'density': round(count / total, 5),
            }

        weather_results = {}
        for weather_type, vocab in WEATHER_VOCAB.items():
            count = sum(1 for w in all_words if w in vocab)
            weather_results[weather_type] = {
                'count': count,
                'density': round(count / total, 5),
            }

        dominant_season = max(season_results, key=lambda k: season_results[k]['density'])
        dominant_weather = max(weather_results, key=lambda k: weather_results[k]['density'])

        total_hits = (sum(s['count'] for s in season_results.values())
                      + sum(w['count'] for w in weather_results.values()))
        density = total_hits / total

        score = min(1.0, density * 10)

        return {
            'score': round(score, 3),
            'method': 'Seasonal & Weather Symbolism (Foster)',
            'season_results': season_results,
            'weather_results': weather_results,
            'dominant_season': dominant_season,
            'dominant_weather': dominant_weather,
            'elemental_density': round(density, 4),
            'precedent': (
                "Foster: Rain cleanses or drowns. Snow is purity or death. "
                "Spring = youth, Summer = passion, Autumn = decline, Winter = death. "
                "Weather is never 'just weather' in literature."
            ),
            'interpretation': (
                f"Dominant season: {dominant_season} "
                f"({season_results[dominant_season]['density']:.1%}). "
                f"Dominant weather: {dominant_weather} "
                f"({weather_results[dominant_weather]['density']:.1%})."
            ),
        }

    def analyze_intertextual_density(self) -> dict:
        """
        METHOD: Intertextual Density
        SOURCES: Foster (How to Read Literature), Pinsky (Singing School)

        Detect cross-reference markers and allusion density.
        """
        cross_ref_vocab = {
            'echo', 'allusion', 'reference', 'reminiscent', 'recalls',
            'evokes', 'invokes', 'resembles', 'parallel', 'compare',
            'contrast', 'like', 'as in', 'similar', 'analogy', 'homage',
        }
        literary_names = {
            'shakespeare', 'homer', 'dante', 'milton', 'virgil', 'ovid',
            'chaucer', 'spenser', 'donne', 'marvell', 'keats', 'shelley',
            'byron', 'wordsworth', 'coleridge', 'blake', 'whitman',
            'dickinson', 'frost', 'eliot', 'yeats', 'auden', 'stevens',
            'bishop', 'plath', 'hughes', 'rilke', 'neruda', 'rumi',
            'sappho', 'horace', 'catullus', 'petrarch', 'baudelaire',
        }

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)

        ref_count = sum(1 for w in all_words if w in cross_ref_vocab)
        name_count = sum(1 for w in all_words if w in literary_names)
        names_found = set(w for w in all_words if w in literary_names)

        density = (ref_count + name_count) / total

        score = min(1.0, density * 20 + len(names_found) * 0.1)

        return {
            'score': round(score, 3),
            'method': 'Intertextual Density (Foster/Pinsky)',
            'reference_vocabulary_count': ref_count,
            'literary_names_found': list(names_found),
            'literary_name_count': name_count,
            'intertextual_density': round(density, 5),
            'precedent': (
                "Foster: All literature grows from other literature. Recognizing "
                "the conversation between texts unlocks layers of meaning. "
                "Pinsky: Remote historical models prevent mere aping of "
                "contemporaries."
            ),
            'interpretation': (
                f"Intertextual density: {density:.2%}. "
                f"{'Explicitly referential' if density > 0.01 else 'Implicitly allusive' if name_count > 0 else 'Self-contained'}. "
                f"Literary names: {', '.join(names_found) if names_found else 'none detected'}."
            ),
        }

    # ==================================================================
    # VI. SPEAKER & PERFORMANCE
    # ==================================================================

    def analyze_dramatic_monologue(self) -> dict:
        """
        METHOD: Dramatic Monologue Detection
        SOURCES: Foster (How to Read Poetry), Pinsky (Singing School)

        Detect persona, implied audience, and dramatic situation markers.
        """
        all_words = [w.lower() for w in self.words]

        # First person markers
        first_person = sum(1 for w in all_words if w in ('i', 'me', 'my', 'mine', 'myself', 'we', 'us', 'our'))
        # Second person (implies addressed audience)
        second_person = sum(1 for w in all_words if w in ('you', 'your', 'yours', 'yourself', 'thou', 'thee', 'thy'))
        # Third person narrative
        third_person = sum(1 for w in all_words if w in ('he', 'she', 'they', 'him', 'her', 'his', 'their'))

        total = max(len(all_words), 1)

        # Determine dominant voice
        if first_person > second_person and first_person > third_person:
            voice = 'first person (lyric I)'
        elif second_person > first_person:
            voice = 'second person (addressed)'
        elif third_person > first_person and third_person > second_person:
            voice = 'third person (narrative)'
        else:
            voice = 'mixed'

        # Dramatic monologue indicators
        dm_markers = {
            'listen', 'hear', 'look', 'see', 'come', 'let me', 'allow me',
            'suppose', 'imagine', 'picture', 'consider', 'mark',
        }
        dm_count = sum(1 for w in all_words if w in dm_markers)

        # Check for dramatic situation markers
        situation_vocab = {
            'here', 'now', 'tonight', 'today', 'this room', 'this place',
            'before us', 'among us', 'between us',
        }
        situation_count = sum(1 for sent in self.sentences
                              for w in word_tokenize(sent.lower())
                              if w in situation_vocab)

        is_dramatic_monologue = (first_person > 3 and second_person > 1 and dm_count > 0)

        score = min(1.0, (first_person + second_person) / total * 5
                    + dm_count * 0.1 + (0.3 if is_dramatic_monologue else 0))

        return {
            'score': round(score, 3),
            'method': 'Dramatic Monologue Detection (Foster/Pinsky)',
            'first_person_count': first_person,
            'second_person_count': second_person,
            'third_person_count': third_person,
            'dominant_voice': voice,
            'dramatic_monologue_markers': dm_count,
            'situation_markers': situation_count,
            'is_dramatic_monologue': is_dramatic_monologue,
            'precedent': (
                "Foster: Distinguish between the poet and the speaker. Pinsky: "
                "Ransom's 'credulous, naïve balladeer' in 'Captain Carpenter' "
                "is an invented narrator, not Ransom himself."
            ),
            'interpretation': (
                f"Dominant voice: {voice}. "
                f"{'Dramatic monologue likely' if is_dramatic_monologue else 'Not a clear dramatic monologue'}. "
                f"1st: {first_person}, 2nd: {second_person}, 3rd: {third_person}."
            ),
        }

    def analyze_apostrophe(self) -> dict:
        """
        METHOD: Apostrophe & Address Detection
        SOURCES: Hollander (Rhyme's Reason), Foster (How to Read Poetry)

        Detect direct address to absent, abstract, or non-human entities.
        """
        apostrophe_markers = re.findall(
            r'\b[Oo]\s+[A-Z]\w+|\b[Oo]h?\s+(?:my|thou|you|dear|sweet|blessed|holy)',
            self.text,
        )

        # Imperative address
        imperative_pattern = re.findall(
            r'^(?:Come|Go|Rise|Hear|Listen|Look|See|Behold|Remember|Forget|Wake|Sleep|Sing|Tell|Give|Take|Let)',
            self.text,
            re.MULTILINE,
        )

        # Address to abstractions
        abstract_address = re.findall(
            r'\b(?:O|Oh|Ah)\s+(?:Death|Love|Time|Beauty|Night|Darkness|Light|Fortune|Fate|Nature|World|Life)',
            self.text,
            re.IGNORECASE,
        )

        total_apostrophe = len(apostrophe_markers) + len(abstract_address)
        total_imperative = len(imperative_pattern)

        score = min(1.0, total_apostrophe * 0.15 + total_imperative * 0.05)

        return {
            'score': round(score, 3),
            'method': 'Apostrophe & Address (Hollander/Foster)',
            'apostrophe_markers': apostrophe_markers[:10],
            'abstract_addresses': abstract_address[:10],
            'imperative_openings': imperative_pattern[:10],
            'total_apostrophes': total_apostrophe,
            'total_imperatives': total_imperative,
            'precedent': (
                "Hollander: Apostrophe transforms the absent into the present "
                "through the sheer force of address. Foster: Direct address to "
                "abstractions is one of poetry's distinctive powers."
            ),
            'interpretation': (
                f"{total_apostrophe} apostrophic addresses, "
                f"{total_imperative} imperative openings. "
                f"{'Strong vocative/apostrophic texture.' if total_apostrophe > 3 else 'Some direct address.' if total_apostrophe > 0 else 'No apostrophe detected.'}"
            ),
        }

    def analyze_tone(self) -> dict:
        """
        METHOD: Tone Classification
        SOURCES: Ciardi (How Does a Poem Mean), Foster (How to Read Poetry)

        Classify the emotional register through vocabulary analysis.
        """
        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)

        tone_scores = {}
        for tone, vocab in TONE_CLUSTERS.items():
            hits = sum(1 for w in all_words if w in vocab)
            tone_scores[tone] = {
                'count': hits,
                'density': round(hits / total, 5),
            }

        ranked = sorted(tone_scores.items(), key=lambda x: -x[1]['density'])
        dominant_tone = ranked[0][0] if ranked else 'neutral'
        secondary_tone = ranked[1][0] if len(ranked) > 1 else 'none'

        # Tone complexity: multiple active tones = complex emotional register
        active_tones = sum(1 for t in tone_scores.values() if t['density'] > 0.005)

        score = min(1.0, tone_scores[dominant_tone]['density'] * 20 + active_tones * 0.05)

        return {
            'score': round(score, 3),
            'method': 'Tone Classification (Ciardi/Foster)',
            'tone_scores': {k: v for k, v in ranked},
            'dominant_tone': dominant_tone,
            'secondary_tone': secondary_tone,
            'active_tones': active_tones,
            'tone_complexity': 'complex' if active_tones >= 3 else 'moderate' if active_tones == 2 else 'simple',
            'precedent': (
                "Ciardi: Tone is the poet's attitude toward subject — reverent, "
                "ironic, mocking, tender. Foster: Tone shifts signal the poem's "
                "deeper moves."
            ),
            'interpretation': (
                f"Dominant tone: {dominant_tone}, secondary: {secondary_tone}. "
                f"{active_tones} tonal registers active. "
                f"Emotional complexity: {'complex' if active_tones >= 3 else 'moderate' if active_tones == 2 else 'simple'}."
            ),
        }

    def analyze_persona_markers(self) -> dict:
        """
        METHOD: Persona vs. Poet Markers
        SOURCES: Pinsky (Singing School), Foster (How to Read Poetry)

        Detect signals that the speaker is an adopted voice, not the poet.
        """
        # Persona markers: specific names, dramatic situations, contradiction with known biographical facts
        persona_vocab = {
            'character', 'role', 'mask', 'persona', 'voice', 'guise',
            'pretend', 'suppose', 'imagine', 'if i were', 'as if',
            'playing', 'acting', 'speaking as', 'in the voice of',
        }

        # Framing devices
        framing_patterns = [
            r'"[^"]{20,}"',  # Extended quoted speech
            r"'[^']{20,}'",  # Extended quoted speech
            r'\bsaid\b|\bsays\b|\bspoke\b|\bspeaks\b',
        ]

        all_words = [w.lower() for w in self.words if w.isalpha()]
        total = max(len(all_words), 1)

        persona_hits = sum(1 for w in all_words if w in persona_vocab)
        frame_hits = sum(len(re.findall(p, self.text)) for p in framing_patterns)

        # Character names (proper nouns in context of speech)
        tagged = pos_tag(self.words)
        proper_nouns = [w for w, t in tagged if t == 'NNP' and w[0].isupper()]
        unique_names = len(set(proper_nouns))

        adopted_voice = persona_hits > 2 or frame_hits > 3 or unique_names > 5

        score = min(1.0, persona_hits * 0.1 + frame_hits * 0.05 + unique_names * 0.02)

        return {
            'score': round(score, 3),
            'method': 'Persona vs. Poet Markers (Pinsky/Foster)',
            'persona_vocabulary_hits': persona_hits,
            'framing_device_count': frame_hits,
            'unique_proper_nouns': unique_names,
            'adopted_voice_likely': adopted_voice,
            'precedent': (
                "Pinsky: The invented narrator creates distance between poet and "
                "speaker. Foster: Always distinguish the poet from the speaker — "
                "the speaker is a creation, not a confession."
            ),
            'interpretation': (
                f"{'Adopted voice likely' if adopted_voice else 'Direct lyric voice likely'}. "
                f"Persona markers: {persona_hits}, Framing devices: {frame_hits}, "
                f"Named characters: {unique_names}."
            ),
        }

    # ==================================================================
    # VII. SHARED METHODS (from Esoteric Analyzer)
    # ==================================================================

    def analyze_contradiction(self) -> dict:
        """
        METHOD: Contradiction Analysis (shared from Esoteric Analyzer)
        SOURCES: Strauss, Melzer; Pinsky (Singing School: paradox as feature),
                 Foster (How to Read Literature: irony as master trope)

        Detect semantic tension between passages.
        """
        if len(self.paragraphs) < 2:
            return {'score': 0, 'method': 'Contradiction Analysis'}

        affirmation_words = {
            'all', 'every', 'always', 'never', 'none', 'nothing', 'certainly',
            'undoubtedly', 'absolutely', 'must', 'true', 'truth', 'clear',
        }
        negation_words = {
            'but', 'however', 'yet', 'though', 'although', 'nevertheless',
            'not', 'never', 'no', 'nor', 'neither', 'hardly', 'scarcely',
            'except', 'unless', 'despite', 'contrary',
        }

        tensions = []
        for i in range(len(self.paragraphs)):
            for j in range(i + 1, min(i + 5, len(self.paragraphs))):
                words_i = set(w.lower() for w in word_tokenize(self.paragraphs[i]) if w.isalpha())
                words_j = set(w.lower() for w in word_tokenize(self.paragraphs[j]) if w.isalpha())

                # Shared topic vocabulary (they discuss the same thing)
                shared = words_i & words_j
                if len(shared) < 3:
                    continue

                # One affirms, other negates
                affirm_i = len(words_i & affirmation_words)
                negate_i = len(words_i & negation_words)
                affirm_j = len(words_j & affirmation_words)
                negate_j = len(words_j & negation_words)

                tension = abs((affirm_i - negate_i) - (affirm_j - negate_j))
                if tension > 2:
                    tensions.append({
                        'para_a': i + 1,
                        'para_b': j + 1,
                        'tension_score': tension,
                        'shared_topic': list(shared)[:5],
                        'excerpt_a': self.paragraphs[i][:100],
                        'excerpt_b': self.paragraphs[j][:100],
                    })

        tensions.sort(key=lambda x: -x['tension_score'])
        score = min(1.0, len(tensions) * 0.1)

        return {
            'score': round(score, 3),
            'method': 'Contradiction Analysis (Strauss/Pinsky/Foster)',
            'tensions': tensions[:10],
            'total_tensions': len(tensions),
            'precedent': (
                "Strauss: Contradictions in careful writers are deliberate signals. "
                "Pinsky: Shakespeare's 'two distinct, division none' holds paradox "
                "without resolution. Foster: The best literature embraces "
                "contradiction rather than resolving it."
            ),
            'interpretation': (
                f"{len(tensions)} passage tensions detected. "
                f"{'Significant contradictory texture.' if len(tensions) > 5 else 'Some tension present.' if tensions else 'No notable contradictions.'}"
            ),
        }

    def analyze_irony_detection(self) -> dict:
        """
        METHOD: Irony Detection (shared from Esoteric Analyzer)
        SOURCES: Strauss; Foster (How to Read Literature: irony as master framework)

        Detect sentiment inversion and ironic markers.
        """
        praise_words = {
            'noble', 'excellent', 'wise', 'great', 'admirable', 'wonderful',
            'magnificent', 'perfect', 'brilliant', 'glorious', 'superb',
            'best', 'finest', 'greatest', 'beautiful', 'virtuous', 'blessed',
        }
        qualifier_words = {
            'perhaps', 'maybe', 'somewhat', 'rather', 'quite', 'apparently',
            'seemingly', 'ostensibly', 'supposedly', 'allegedly', 'so-called',
            'of course', 'naturally', 'needless to say',
        }
        negation_in_praise = {
            'not without', 'hardly lacking', 'scarcely devoid', 'no small',
        }

        irony_markers = []
        for i, sent in enumerate(self.sentences):
            words = set(w.lower() for w in word_tokenize(sent) if w.isalpha())
            praise = len(words & praise_words)
            qualifiers = len(words & qualifier_words)

            if praise > 0 and qualifiers > 0:
                irony_markers.append({
                    'sentence': i + 1,
                    'text': sent[:150],
                    'praise_words': praise,
                    'qualifier_words': qualifiers,
                })

            # Check for negation-in-praise patterns
            for pattern in negation_in_praise:
                if pattern in sent.lower():
                    irony_markers.append({
                        'sentence': i + 1,
                        'text': sent[:150],
                        'pattern': pattern,
                        'praise_words': praise,
                        'qualifier_words': qualifiers,
                    })

        score = min(1.0, len(irony_markers) * 0.08)

        return {
            'score': round(score, 3),
            'method': 'Irony Detection (Strauss/Foster)',
            'irony_markers': irony_markers[:15],
            'total_irony_markers': len(irony_markers),
            'precedent': (
                "Foster: Irony trumps everything — it can invert any symbolic "
                "reading. It is the master trope of modern literature. "
                "Strauss: Ironic praise is the careful reader's first signal "
                "that the surface is not to be trusted."
            ),
            'interpretation': (
                f"{len(irony_markers)} potential irony markers. "
                f"{'Strong ironic texture.' if len(irony_markers) > 8 else 'Some ironic signals.' if irony_markers else 'No clear ironic markers.'}"
            ),
        }

    def analyze_silence(self) -> dict:
        """
        METHOD: Silence & Omission Analysis (shared from Esoteric Analyzer)
        SOURCES: Strauss; Pinsky (Singing School: Moore's restraint)

        Detect expected but absent topics.
        """
        if not self.expected_topics:
            return {
                'score': 0,
                'method': 'Silence & Omission Analysis (Strauss/Pinsky)',
                'absent_topics': [],
                'rare_topics': [],
                'interpretation': 'No expected topics provided. Use set_expected_topics().',
            }

        all_words = set(w.lower() for w in self.words if w.isalpha())
        word_freq = Counter(w.lower() for w in self.words if w.isalpha())
        total = max(len(self.words), 1)

        absent = [t for t in self.expected_topics if t.lower() not in all_words]
        rare = [t for t in self.expected_topics
                if t.lower() in all_words and word_freq[t.lower()] / total < 0.001]

        absence_ratio = len(absent) / max(len(self.expected_topics), 1)
        score = min(1.0, absence_ratio * 1.5)

        return {
            'score': round(score, 3),
            'method': 'Silence & Omission Analysis (Strauss/Pinsky)',
            'absent_topics': absent,
            'rare_topics': rare,
            'absence_ratio': round(absence_ratio, 3),
            'precedent': (
                "Strauss: Conspicuous silence is the most powerful esoteric "
                "technique. Pinsky: Moore's 'the deepest feeling always shows "
                "itself in silence; not in silence, but restraint.'"
            ),
            'interpretation': (
                f"{len(absent)} expected topics absent, {len(rare)} present but rare. "
                f"Absence ratio: {absence_ratio:.0%}."
            ),
        }

    def analyze_polysemy_shared(self) -> dict:
        """
        METHOD: Polysemy Detection (shared from Esoteric Analyzer)
        SOURCES: Dante (four levels), Pinsky (Singing School: ambiguity as feature)

        Words operating across multiple semantic domains.
        """
        semantic_domains = {
            'political': {'power', 'rule', 'law', 'order', 'state', 'govern',
                          'authority', 'liberty', 'justice', 'right', 'citizen'},
            'religious': {'god', 'soul', 'spirit', 'grace', 'sin', 'holy',
                          'sacred', 'divine', 'prayer', 'faith', 'heaven'},
            'erotic': {'love', 'desire', 'beauty', 'passion', 'flame', 'burn',
                       'kiss', 'embrace', 'heart', 'sweet', 'tender'},
            'natural': {'sun', 'moon', 'star', 'earth', 'water', 'fire',
                        'tree', 'flower', 'river', 'mountain', 'wind'},
            'philosophical': {'truth', 'being', 'nothing', 'essence', 'form',
                              'idea', 'reason', 'mind', 'knowledge', 'wisdom'},
        }

        all_words = set(w.lower() for w in self.words if w.isalpha())

        # Find words that appear in multiple domains
        cross_domain = {}
        for word in all_words:
            domains = [d for d, vocab in semantic_domains.items() if word in vocab]
            if len(domains) >= 2:
                cross_domain[word] = domains

        # Paragraph-level multi-domain density
        multi_domain_paras = []
        for i, para in enumerate(self.paragraphs):
            para_words = set(w.lower() for w in word_tokenize(para) if w.isalpha())
            domains_present = set()
            for word in para_words:
                for d, vocab in semantic_domains.items():
                    if word in vocab:
                        domains_present.add(d)
            if len(domains_present) >= 3:
                multi_domain_paras.append({
                    'paragraph': i + 1,
                    'domains': list(domains_present),
                    'domain_count': len(domains_present),
                })

        score = min(1.0, len(cross_domain) * 0.05 + len(multi_domain_paras) * 0.1)

        return {
            'score': round(score, 3),
            'method': 'Polysemy Detection (Dante/Pinsky)',
            'cross_domain_words': cross_domain,
            'multi_domain_paragraphs': multi_domain_paras[:10],
            'total_cross_domain_words': len(cross_domain),
            'total_multi_domain_paragraphs': len(multi_domain_paras),
            'precedent': (
                "Dante: A text operates on literal, allegorical, moral, and "
                "anagogical levels simultaneously. Pinsky: Ambiguity is a feature, "
                "not a bug — 'Was it uncertain memory or uncertain paternity?'"
            ),
            'interpretation': (
                f"{len(cross_domain)} cross-domain words, "
                f"{len(multi_domain_paras)} multi-domain paragraphs. "
                f"{'Rich polysemic texture.' if len(cross_domain) > 5 else 'Some multi-level vocabulary.' if cross_domain else 'Limited polysemy.'}"
            ),
        }

    def analyze_symmetry_shared(self) -> dict:
        """
        METHOD: Structural Symmetry (shared from Esoteric Analyzer)
        SOURCES: Strauss, Benardete; Hollander (ring/chiastic forms)

        Detect mirror structures and chiastic patterns.
        """
        if len(self.stanzas) < 3:
            return {'score': 0, 'method': 'Structural Symmetry'}

        # Compare first and last stanzas, second and second-to-last, etc.
        mirror_scores = []
        n = len(self.stanzas)
        for i in range(n // 2):
            j = n - 1 - i
            words_i = set(w.lower() for w in word_tokenize(' '.join(self.stanzas[i])) if w.isalpha())
            words_j = set(w.lower() for w in word_tokenize(' '.join(self.stanzas[j])) if w.isalpha())

            if not words_i or not words_j:
                continue

            overlap = len(words_i & words_j)
            total = len(words_i | words_j)
            similarity = overlap / max(total, 1)
            mirror_scores.append({
                'stanza_a': i + 1,
                'stanza_b': j + 1,
                'similarity': round(similarity, 3),
            })

        avg_mirror = sum(m['similarity'] for m in mirror_scores) / max(len(mirror_scores), 1)
        score = min(1.0, avg_mirror * 3)

        return {
            'score': round(score, 3),
            'method': 'Structural Symmetry (Strauss/Hollander)',
            'mirror_pairs': mirror_scores,
            'average_mirror_similarity': round(avg_mirror, 3),
            'precedent': (
                "Strauss: Ring composition hides the crucial content at the "
                "center. Hollander: Chiastic structures create X-shaped "
                "crossing of elements."
            ),
            'interpretation': (
                f"Average mirror similarity: {avg_mirror:.0%}. "
                f"{'Strong ring/chiastic structure.' if avg_mirror > 0.3 else 'Some mirroring.' if avg_mirror > 0.1 else 'No notable symmetry.'}"
            ),
        }

    # ==================================================================
    # COLLECTION / POEM SPLITTING
    # ==================================================================

    def split_poems(self) -> list[dict]:
        """Split a collection into individual poems or stories/chapters.

        Strategies (tried in order, first to produce 3+ results wins):
        1. Bracketed EPUB title links [TITLE](link)
        2. Markdown headings (## or ###)
        3. --- EPUB file boundary separators
        4. Inline Roman/Arabic numeral markers
        5. Anthology format (ALL CAPS author + dated headings)
        6. Prose chapter detection (Chapter X, Part X, ALL CAPS titles, TOC-based)
        7. Within-section splitting (blank line + capitalized first line)
        8. Triple+ newline fallback
        9. Force-split for large unsplittable texts

        Post-processing: merge over-split results, merge tiny sections.

        Returns list of {"title": str, "text": str, "index": int, "author"?: str}
        """
        poems = self._split_bracketed_titles()
        if len(poems) >= 3:
            return self._postprocess(poems)

        poems = self._split_markdown_headings()
        if len(poems) >= 3:
            poems = self._refine_large_sections(poems)
            return self._postprocess(poems)

        poems = self._split_separator_markers()
        if len(poems) >= 3:
            return self._postprocess(poems)

        poems = self._split_inline_numerals()
        if len(poems) >= 3:
            return self._postprocess(poems)

        poems = self._split_anthology_authors()
        if len(poems) >= 3:
            return self._postprocess(poems)

        poems = self._split_prose_chapters()
        if len(poems) >= 3:
            return self._postprocess(poems)

        poems = self._split_blank_line_poems()
        if len(poems) >= 3:
            return self._postprocess(poems)

        poems = self._split_triple_newlines()
        if len(poems) >= 3:
            return self._postprocess(poems)

        # Final fallback: force-split large texts into equal sections
        return self._force_split()

    def _postprocess(self, sections: list[dict]) -> list[dict]:
        """Post-process split results to fix over-splitting and tiny sections.

        Rules:
        1. If >300 sections, merge adjacent small ones (<1000 chars) together
        2. If avg section size < 300 chars, re-merge until avg > 500
        3. Re-index after merging
        """
        if not sections:
            return sections

        # Rule 1: Over-split — merge adjacent small sections
        if len(sections) > 300:
            merged = []
            buffer_title = None
            buffer_text = []
            for s in sections:
                if len(s['text']) < 1000 and buffer_text:
                    buffer_text.append(s['text'])
                elif len(s['text']) < 1000 and not buffer_text:
                    buffer_title = s.get('title', '')
                    buffer_text.append(s['text'])
                else:
                    if buffer_text:
                        merged.append({
                            "title": buffer_title or f"Section {len(merged) + 1}",
                            "text": '\n\n'.join(buffer_text),
                            "index": len(merged),
                        })
                        buffer_text = []
                        buffer_title = None
                    merged.append(s)
            if buffer_text:
                merged.append({
                    "title": buffer_title or f"Section {len(merged) + 1}",
                    "text": '\n\n'.join(buffer_text),
                    "index": len(merged),
                })
            sections = merged

        # Rule 2: Tiny sections — merge until avg > 500 chars
        sizes = [len(s['text']) for s in sections]
        avg = sum(sizes) / max(len(sizes), 1)
        if avg < 300 and len(sections) > 5:
            # Group sections into larger chunks
            target_count = max(3, len(sections) // 5)
            chunk_size = max(1, len(sections) // target_count)
            merged = []
            for i in range(0, len(sections), chunk_size):
                chunk = sections[i:i + chunk_size]
                title = chunk[0].get('title', f'Section {len(merged) + 1}')
                body = '\n\n'.join(s['text'] for s in chunk)
                merged.append({"title": title, "text": body, "index": len(merged)})
            sections = merged

        # Re-index
        for i, s in enumerate(sections):
            s['index'] = i

        return sections

    def _force_split(self) -> list[dict]:
        """Last resort: split large unsplittable text into ~10 equal sections."""
        text = self.text.strip()
        if len(text) < 5000:
            return [{"title": self.title or "Full Text", "text": text, "index": 0}]

        # Split into paragraphs, then group into ~10 sections
        paras = re.split(r'\n\s*\n', text)
        paras = [p.strip() for p in paras if p.strip()]
        if len(paras) < 5:
            return [{"title": self.title or "Full Text", "text": text, "index": 0}]

        target = min(max(5, len(paras) // 20), 15)
        chunk_size = max(1, len(paras) // target)
        sections = []
        for i in range(0, len(paras), chunk_size):
            chunk = paras[i:i + chunk_size]
            body = '\n\n'.join(chunk)
            # Title from first sentence
            first = chunk[0][:60].split('.')[0].strip()
            sections.append({
                "title": first if len(first) > 5 else f"Section {len(sections) + 1}",
                "text": body,
                "index": len(sections),
            })
        return sections

    def _split_bracketed_titles(self) -> list[dict]:
        """Strategy 1: [POEM TITLE](link) — common in EPUB exports."""
        # Match both ALL CAPS and mixed case bracketed titles
        bracket_pattern = re.compile(
            r'^\[([A-Za-z][A-Za-z\s\-\'\,\.\:\;\!\?0-9]+)\]\([^\)]+\)\s*$',
            re.MULTILINE,
        )
        matches = list(bracket_pattern.finditer(self.text))
        if len(matches) < 5:
            return []

        SKIP = {'CONTENTS', 'COVER', 'TITLE PAGE', 'DEDICATION', 'EPIGRAPH',
                'ACKNOWLEDGMENT', 'COPYRIGHT', 'OCEANOFPDF', 'ONE', 'TWO',
                'THREE', 'FOUR', 'FIVE', 'SIX', 'NOTES', 'INDEX', 'ABOUT'}
        poems = []
        for i, m in enumerate(matches):
            title = m.group(1).strip()
            if any(skip in title.upper() for skip in SKIP):
                continue
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(self.text)
            body = self.text[start:end].strip()
            body = re.sub(r'\[\*OceanofPDF\.com\*\]\([^\)]+\)', '', body).strip()
            if len(body) < 20:
                continue
            poems.append({"title": title.title(), "text": body, "index": len(poems)})
        return poems

    def _split_markdown_headings(self) -> list[dict]:
        """Strategy 2: ## or ### headings."""
        heading_pattern = re.compile(r'^(#{2,3})\s+(.+)$', re.MULTILINE)
        matches = list(heading_pattern.finditer(self.text))
        if len(matches) < 3:
            return []

        poems = []
        for i, m in enumerate(matches):
            title = m.group(2).strip()
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(self.text)
            body = self.text[start:end].strip()
            if not body or len(body) < 20:
                continue
            poems.append({"title": title[:60], "text": body, "index": len(poems)})
        return poems

    def _split_separator_markers(self) -> list[dict]:
        """Strategy 3: --- EPUB file boundary separators."""
        if '\n---\n' not in self.text:
            return []
        chunks = self.text.split('\n---\n')
        poems = []
        for chunk in chunks:
            chunk = chunk.strip()
            if len(chunk) < 20:
                continue
            first_lines = [l for l in chunk.split('\n') if l.strip()]
            if first_lines and len(first_lines[0]) < 60:
                title = first_lines[0].strip().lstrip('#').strip()
                body = '\n'.join(first_lines[1:]).strip() if len(first_lines) > 1 else chunk
            else:
                title = f"Poem {len(poems) + 1}"
                body = chunk
            if len(body) > 20:
                poems.append({"title": title, "text": body, "index": len(poems)})
        return poems

    def _split_inline_numerals(self) -> list[dict]:
        """Strategy 4: Inline Roman/Arabic numeral markers (iii. xxvii. 16.)."""
        inline = re.compile(r'(?:^|\s)([ivxlcdm]{1,6})\.\s+(?=[a-z])', re.MULTILINE)
        arabic = re.compile(r'(?:^|\s)(\d{1,3})\.\s+(?=[a-zA-Z])', re.MULTILINE)
        markers = [(m.start(), m.group(1), m.end()) for m in inline.finditer(self.text)]
        markers += [(m.start(), m.group(1), m.end()) for m in arabic.finditer(self.text)]
        markers.sort(key=lambda x: x[0])
        if len(markers) < 3:
            return []

        poems = []
        for i, (start, numeral, text_start) in enumerate(markers):
            end = markers[i + 1][0] if i + 1 < len(markers) else len(self.text)
            body = self.text[text_start:end].strip()
            if len(body) >= 20:
                poems.append({"title": numeral, "text": body, "index": len(poems)})
        return poems

    def _split_anthology_authors(self) -> list[dict]:
        """Strategy 5: ALL CAPS author headings with dates."""
        author_pat = re.compile(
            r'^([A-Z][A-Z\s\.\-\']{3,})\s*\(\s*(?:b\.\s*)?\d{4}\s*[-–]\s*(?:\d{4})?\s*\)',
            re.MULTILINE,
        )
        matches = list(author_pat.finditer(self.text))
        if len(matches) < 5:
            return []

        poems = []
        for i, am in enumerate(matches):
            author_name = am.group(1).strip().title()
            start = am.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(self.text)
            section = self.text[start:end].strip()
            if len(section) < 50:
                continue

            # Try to split within author section by poem titles
            title_pat = re.compile(r'^([A-Z][A-Za-z\s\'\"\,\-\.\:\;\!\?]+?)\s+\d{3,4}\s*$', re.MULTILINE)
            titles = list(title_pat.finditer(section))
            if titles:
                for j, tm in enumerate(titles):
                    poem_title = tm.group(1).strip()
                    if poem_title.upper() == poem_title or len(poem_title) < 3:
                        continue
                    p_start = tm.end()
                    p_end = titles[j + 1].start() if j + 1 < len(titles) else len(section)
                    body = re.sub(r'\s+\d{3,4}\s*$', '', section[p_start:p_end].strip(), flags=re.MULTILINE)
                    if len(body) >= 20:
                        poems.append({"title": f"{poem_title} ({author_name})", "text": body,
                                      "index": len(poems), "author": author_name})
            else:
                poems.append({"title": f"Poems by {author_name}", "text": section,
                              "index": len(poems), "author": author_name})
        return poems

    def _split_prose_chapters(self) -> list[dict]:
        """Strategy 6: Prose chapter/story detection.

        Handles:
        - Chapter/Part/Book headings
        - ALL CAPS story titles embedded in text (e.g., Dubliners)
        - TOC-derived title lists used as split markers
        - Story-length blocks separated by significant gaps
        """
        # Strategy 6a: Chapter/Part/Book headings
        chapter_pat = re.compile(
            r'^(?:'
            r'(?:Chapter|CHAPTER|Part|PART|Book|BOOK|Section|SECTION)\s+[\dIVXLCDMivxlcdm]+\.?'
            r'|[IVX]{1,4}\.\s'
            r')\s*(.*)$',
            re.MULTILINE,
        )
        matches = list(chapter_pat.finditer(self.text))
        if len(matches) >= 3:
            chapters = []
            for i, m in enumerate(matches):
                title = m.group(0).strip()
                subtitle = m.group(1).strip() if m.group(1) else ""
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(self.text)
                body = self.text[start:end].strip()
                if len(body) < 100:
                    continue
                full_title = f"{title} {subtitle}".strip() if subtitle else title
                chapters.append({"title": full_title[:60], "text": body, "index": len(chapters)})
            if len(chapters) >= 3:
                return chapters

        # Strategy 6b: ALL CAPS story/section titles embedded in text
        # Detect: "THE SISTERS", "AN ENCOUNTER", "ARABY" as standalone ALL CAPS
        # or preceded by a book title like "DUBLINERS THE SISTERS"
        # Also match ALL CAPS followed by double-newline (story titles in continuous text)
        caps_title_pat = re.compile(
            r'([A-Z][A-Z\s\'\-]{2,40}?)(?=\n\n)',
        )
        caps_matches = list(caps_title_pat.finditer(self.text))
        BOILERPLATE = {'CONTENTS', 'COPYRIGHT', 'ACKNOWLEDGMENTS', 'NOTES', 'INDEX',
                       'ABOUT THE AUTHOR', 'ALSO BY', 'DEDICATION', 'DISCLAIMER',
                       'TM ETEXTS', 'DISCLAIMER OF DAMAGES', 'YOU USE', 'NO REMEDIES'}
        valid_caps = []
        for m in caps_matches:
            title = m.group(1).strip()
            words = title.split()
            if not all(w.isalpha() or w in ("'", "-") for w in words):
                continue
            if any(b in title for b in BOILERPLATE):
                continue
            if 1 <= len(words) <= 8 and len(title) >= 4:
                # Strip book-title prefix if present (e.g., "DUBLINERS THE SISTERS" -> "THE SISTERS")
                # Heuristic: if first word appears only once in titles, it's a prefix
                valid_caps.append((m.start(), title))

        if len(valid_caps) >= 5:
            chapters = []
            for i, (pos, title) in enumerate(valid_caps):
                start = pos + len(title) + 1
                end = valid_caps[i + 1][0] if i + 1 < len(valid_caps) else len(self.text)
                body = self.text[start:end].strip()
                if len(body) < 200:
                    continue
                chapters.append({"title": title.title(), "text": body, "index": len(chapters)})
            if len(chapters) >= 5:
                return chapters

        # Strategy 6c: Extract titles from embedded TOC and use as split markers
        # Look for a block of short Title Case lines (TOC)
        toc_pat = re.compile(r'(?:CONTENTS|Contents)\s*\n((?:[^\n]{5,50}\n){3,30})', re.MULTILINE)
        toc_match = toc_pat.search(self.text)
        if toc_match:
            toc_text = toc_match.group(1)
            toc_titles = [l.strip() for l in toc_text.split('\n') if l.strip() and len(l.strip()) < 50]
            if len(toc_titles) >= 3:
                chapters = []
                for i, title in enumerate(toc_titles):
                    # Find title in the text (after TOC)
                    search_start = toc_match.end()
                    # Try both exact and ALL CAPS versions
                    idx = self.text.find(title, search_start)
                    if idx < 0:
                        idx = self.text.find(title.upper(), search_start)
                    if idx < 0:
                        continue
                    start = idx + len(title)
                    # Find next title
                    next_idx = len(self.text)
                    for next_title in toc_titles[i+1:]:
                        ni = self.text.find(next_title, start)
                        if ni < 0:
                            ni = self.text.find(next_title.upper(), start)
                        if ni >= 0:
                            next_idx = ni
                            break
                    body = self.text[start:next_idx].strip()
                    if len(body) >= 100:
                        chapters.append({"title": title, "text": body, "index": len(chapters)})
                if len(chapters) >= 3:
                    return chapters

        # Strategy 6d: Story-length blocks separated by significant gaps
        blocks = re.split(r'\n\s*\n\s*\n', self.text)
        if len(blocks) >= 3:
            chapters = []
            for block in blocks:
                block = block.strip()
                if len(block) < 200:
                    continue
                lines = block.split('\n')
                first = lines[0].strip()
                if len(first) < 60 and first[0:1].isupper() and len(lines) > 3:
                    title = first
                    body = '\n'.join(lines[1:]).strip()
                else:
                    title = f"Chapter {len(chapters) + 1}"
                    body = block
                chapters.append({"title": title, "text": body, "index": len(chapters)})
            if len(chapters) >= 3:
                return chapters
        return []

    def _split_blank_line_poems(self) -> list[dict]:
        """Strategy 7: Within-section splitting for collections like Dickinson.

        Poems separated by blank lines where each poem starts with a capitalized line
        and is 3-40 lines long.
        """
        # Split on double+ blank lines
        blocks = re.split(r'\n\s*\n', self.text)
        poems = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = [l for l in block.split('\n') if l.strip()]
            # A poem-like block: 2-50 lines, first line capitalized, not a heading
            if 2 <= len(lines) <= 50 and lines[0][0:1].isupper() and not lines[0].startswith('#'):
                title = lines[0][:50].rstrip(',;:—-').strip()
                poems.append({"title": title, "text": block, "index": len(poems)})
            elif len(lines) == 1 and len(lines[0]) > 30:
                # Single long line = might be a prose paragraph, skip
                continue
        return poems if len(poems) >= 3 else []

    def _split_triple_newlines(self) -> list[dict]:
        """Final fallback: split on triple+ newlines."""
        chunks = re.split(r'\n{3,}', self.text)
        poems = []
        for i, chunk in enumerate(chunks):
            chunk = chunk.strip()
            if len(chunk) < 20:
                continue
            lines = chunk.split('\n')
            if len(lines[0]) < 60 and len(lines) > 2:
                title = lines[0].strip()
                body = '\n'.join(lines[1:]).strip()
            else:
                title = f"Section {len(poems) + 1}"
                body = chunk
            poems.append({"title": title, "text": body, "index": len(poems)})
        return poems

    def _refine_large_sections(self, sections: list[dict]) -> list[dict]:
        """Post-process: split very large sections into sub-poems if possible.

        When a section is >10x the median size, try within-section splitting.
        """
        if not sections:
            return sections
        sizes = [len(s['text']) for s in sections]
        median_size = sorted(sizes)[len(sizes) // 2]
        if median_size < 100:
            return sections  # All sections are small, no refinement needed

        refined = []
        for section in sections:
            if len(section['text']) > median_size * 10 and len(section['text']) > 5000:
                # Try to split this large section into sub-poems
                sub_analyzer = LiteraryAnalyzer()
                sub_analyzer.text = section['text']
                sub_analyzer.mode = self.mode
                sub_poems = sub_analyzer._split_blank_line_poems()
                if len(sub_poems) >= 3:
                    for sp in sub_poems:
                        sp['index'] = len(refined)
                        sp['parent_section'] = section['title']
                        refined.append(sp)
                    continue
            refined.append(section)
            section['index'] = len(refined) - 1
        return refined

    def full_collection_analysis(self) -> dict:
        """Analyze a poetry collection — runs per-poem analysis then aggregates.

        Returns:
        {
            "collection_title": str,
            "mode": str,
            "poem_count": int,
            "poems": [{"title": str, "composite_score": float, "analyses": {...}}, ...],
            "collection_summary": {
                "avg_composite": float,
                "dominant_meter": str,
                "dominant_tone": str,
                "common_imagery": list,
                "formal_range": str,
                ...
            }
        }
        """
        poems = self.split_poems()
        if not poems:
            # Not a collection — run single analysis
            return self.full_analysis()

        poem_results = []
        all_meters = []
        all_tones = []
        all_forms = []
        all_scores = []
        all_imagery = Counter()

        for poem in poems:
            # Create a fresh analyzer for each poem
            pa = LiteraryAnalyzer()
            pa.load_text_string(poem["text"], title=poem["title"])
            pa.set_mode(self.mode)
            try:
                result = pa.full_analysis()
                poem_results.append({
                    "title": poem["title"],
                    "index": poem["index"],
                    "composite_score": result.get("composite_literary_score", 0),
                    "score_interpretation": result.get("score_interpretation", ""),
                    "analyses": result.get("analyses", {}),
                    "text_statistics": result.get("text_statistics", {}),
                })
                all_scores.append(result.get("composite_literary_score", 0))

                # Aggregate
                meter = result.get("analyses", {}).get("meter", {})
                if meter.get("dominant_pattern"):
                    all_meters.append(meter["dominant_pattern"])

                tone = result.get("analyses", {}).get("tone", {})
                if tone.get("dominant_tone"):
                    all_tones.append(tone["dominant_tone"])

                form = result.get("analyses", {}).get("fixed_form", {})
                if form.get("best_match"):
                    all_forms.append(form["best_match"])

                img = result.get("analyses", {}).get("image_clustering", {})
                if img.get("domain_counts"):
                    for domain, count in img["domain_counts"].items():
                        all_imagery[domain] += count

            except Exception as e:
                poem_results.append({
                    "title": poem["title"],
                    "index": poem["index"],
                    "error": str(e),
                })

        # Collection summary
        summary = {
            "avg_composite": round(sum(all_scores) / max(len(all_scores), 1), 3),
            "max_composite": round(max(all_scores) if all_scores else 0, 3),
            "min_composite": round(min(all_scores) if all_scores else 0, 3),
            "dominant_meter": Counter(all_meters).most_common(1)[0][0] if all_meters else "varied",
            "dominant_tone": Counter(all_tones).most_common(1)[0][0] if all_tones else "varied",
            "forms_used": dict(Counter(all_forms).most_common(5)),
            "dominant_imagery": all_imagery.most_common(5),
            "formal_range": f"{len(set(all_forms))} distinct forms across {len(poems)} poems",
        }

        return {
            "collection_title": self.title,
            "mode": self.mode,
            "poem_count": len(poems),
            "poems": poem_results,
            "collection_summary": summary,
        }

    # ==================================================================
    # FULL ANALYSIS
    # ==================================================================

    def full_analysis(self) -> dict:
        """Run all analyses and produce a composite report."""
        self.results = {
            'title': self.title,
            'mode': self.mode,
            'text_statistics': {
                'total_words': len(self.words),
                'total_sentences': len(self.sentences),
                'total_lines': len(self.lines),
                'total_stanzas': len(self.stanzas),
                'total_paragraphs': len(self.paragraphs),
            },
            'analyses': {},
        }

        analyses = [
            # I. Prosody & Sound
            ('meter', self.analyze_meter),
            ('rhyme_scheme', self.analyze_rhyme_scheme),
            ('alliteration', self.analyze_alliteration),
            ('assonance', self.analyze_assonance),
            ('consonance', self.analyze_consonance),
            ('enjambment', self.analyze_enjambment),
            ('caesura', self.analyze_caesura),
            ('sound_meaning', self.analyze_sound_meaning),
            # II. Form & Structure
            ('fixed_form', self.analyze_fixed_form),
            ('stanza_structure', self.analyze_stanza_structure),
            ('volta', self.analyze_volta),
            ('refrain', self.analyze_refrain),
            ('line_length', self.analyze_line_length),
            ('closure', self.analyze_closure),
            # III. Figurative Language
            ('metaphor_simile', self.analyze_metaphor_simile),
            ('image_clustering', self.analyze_image_clustering),
            ('concrete_abstract', self.analyze_concrete_abstract),
            ('symbol_markers', self.analyze_symbol_markers),
            # IV. Diction & Vocabulary
            ('etymology_register', self.analyze_etymology_register),
            ('vocabulary_richness', self.analyze_vocabulary_richness),
            ('register_mixing', self.analyze_register_mixing),
            ('pos_profile', self.analyze_pos_profile),
            # V. Narrative & Intertextual
            ('archetype', self.analyze_archetype),
            ('allusion', self.analyze_allusion),
            ('seasonal_weather', self.analyze_seasonal_weather),
            ('intertextual', self.analyze_intertextual_density),
            # VI. Speaker & Performance
            ('dramatic_monologue', self.analyze_dramatic_monologue),
            ('apostrophe', self.analyze_apostrophe),
            ('tone', self.analyze_tone),
            ('persona', self.analyze_persona_markers),
            # VII. Shared
            ('contradiction', self.analyze_contradiction),
            ('irony', self.analyze_irony_detection),
            ('silence', self.analyze_silence),
            ('polysemy', self.analyze_polysemy_shared),
            ('symmetry', self.analyze_symmetry_shared),
        ]

        scores = []
        for name, fn in analyses:
            result = fn()
            self.results['analyses'][name] = result
            scores.append(result.get('score', 0))

        # Mode-aware weighting
        # Poetry mode: prosody and form get highest weights
        # Prose mode: narrative, diction, figurative get highest weights
        if self.mode == 'poetry':
            weights = {
                # I. Prosody & Sound (highest in poetry mode)
                'meter': 0.06, 'rhyme_scheme': 0.06, 'alliteration': 0.04,
                'assonance': 0.04, 'consonance': 0.03, 'enjambment': 0.05,
                'caesura': 0.03, 'sound_meaning': 0.03,
                # II. Form & Structure (high)
                'fixed_form': 0.05, 'stanza_structure': 0.04, 'volta': 0.04,
                'refrain': 0.03, 'line_length': 0.03, 'closure': 0.03,
                # III. Figurative Language (medium-high)
                'metaphor_simile': 0.04, 'image_clustering': 0.03,
                'concrete_abstract': 0.02, 'symbol_markers': 0.03,
                # IV. Diction & Vocabulary (medium)
                'etymology_register': 0.02, 'vocabulary_richness': 0.02,
                'register_mixing': 0.02, 'pos_profile': 0.01,
                # V. Narrative & Intertextual (lower in poetry)
                'archetype': 0.02, 'allusion': 0.02, 'seasonal_weather': 0.01,
                'intertextual': 0.01,
                # VI. Speaker & Performance (medium)
                'dramatic_monologue': 0.02, 'apostrophe': 0.02,
                'tone': 0.03, 'persona': 0.01,
                # VII. Shared (medium)
                'contradiction': 0.02, 'irony': 0.03, 'silence': 0.02,
                'polysemy': 0.02, 'symmetry': 0.02,
            }
        else:  # prose mode
            weights = {
                # I. Prosody & Sound (lower in prose)
                'meter': 0.01, 'rhyme_scheme': 0.01, 'alliteration': 0.02,
                'assonance': 0.02, 'consonance': 0.01, 'enjambment': 0.01,
                'caesura': 0.01, 'sound_meaning': 0.02,
                # II. Form & Structure (lower)
                'fixed_form': 0.01, 'stanza_structure': 0.01, 'volta': 0.02,
                'refrain': 0.01, 'line_length': 0.01, 'closure': 0.03,
                # III. Figurative Language (high in prose)
                'metaphor_simile': 0.05, 'image_clustering': 0.04,
                'concrete_abstract': 0.04, 'symbol_markers': 0.05,
                # IV. Diction & Vocabulary (high)
                'etymology_register': 0.04, 'vocabulary_richness': 0.04,
                'register_mixing': 0.04, 'pos_profile': 0.03,
                # V. Narrative & Intertextual (highest in prose)
                'archetype': 0.05, 'allusion': 0.05, 'seasonal_weather': 0.04,
                'intertextual': 0.04,
                # VI. Speaker & Performance (high)
                'dramatic_monologue': 0.04, 'apostrophe': 0.01,
                'tone': 0.04, 'persona': 0.03,
                # VII. Shared (medium-high)
                'contradiction': 0.04, 'irony': 0.05, 'silence': 0.03,
                'polysemy': 0.03, 'symmetry': 0.02,
            }

        composite = 0
        for i, (name, _) in enumerate(analyses):
            composite += scores[i] * weights.get(name, 0.02)

        self.results['composite_literary_score'] = round(min(1.0, composite), 3)
        self.results['score_interpretation'] = self._interpret_composite(composite)

        return self.results

    def _interpret_composite(self, score: float) -> str:
        if score < 0.2:
            return ("SPARE — The text uses few of the detected literary techniques. "
                    "This may indicate minimalist craft, or the techniques may operate "
                    "below computational detection thresholds.")
        elif score < 0.4:
            return ("MODERATE — Some literary craft signals detected. The text "
                    "employs a subset of formal, figurative, and structural techniques. "
                    "LLM close reading will reveal more.")
        elif score < 0.6:
            return ("RICH — Multiple converging literary signals across several domains. "
                    "The text shows deliberate craft in sound, form, imagery, and/or "
                    "diction. Close reading strongly recommended.")
        else:
            return ("DENSE — Strong convergence across many literary domains. "
                    "The text exhibits high density of formal, sonic, figurative, "
                    "and structural craft. This is a text that rewards and demands "
                    "careful, repeated reading.")

    # ==================================================================
    # LLM PROMPT GENERATION
    # ==================================================================

    def generate_llm_prompt(self) -> str:
        """Generate a staged close-reading prompt informed by computational findings."""
        if not self.results:
            self.full_analysis()

        composite = self.results.get('composite_literary_score', 0)

        # Build findings summary
        findings = f"Composite literary score: {composite} ({self.mode} mode)\n"

        for name, analysis in self.results['analyses'].items():
            score = analysis.get('score', 0)
            if score > 0.2:
                method = analysis.get('method', name)
                interp = analysis.get('interpretation', '')
                findings += f"\n### {method} (score: {score})\n{interp}\n"

        mode_label = "poem" if self.mode == 'poetry' else "text"

        prompt = f"""You are a literary scholar trained in close reading, drawing on the methods
of John Ciardi ("How Does a Poem Mean?"), Robert Pinsky ("Singing School"),
John Hollander ("Rhyme's Reason"), and Thomas C. Foster ("How to Read Literature/
Poetry Like a Professor").

You are analyzing: "{self.title}"

A computational pre-analysis has been performed and yielded these findings:

{findings}

---

## HOW TO WRITE THIS ANALYSIS

**Audience and voice.** Write as a scholar speaking to an intelligent non-specialist. Open each stage with a sentence that states what you found, then develop the evidence in paragraphs. Let the prose carry the reader — do not treat stage headers as dry labels. Prefer paragraphs to bullets except for enumerated textual evidence.

**Two-pass method.** Before drafting, survey every stage below and silently mark each as:
- **LOAD-BEARING** — the {mode_label} genuinely activates this method; concrete evidence is available in the text or the computational findings.
- **SUPPORTING** — some evidence exists, worth folding into a load-bearing stage.
- **NOT APPLICABLE** — the {mode_label} does not activate this, or the findings are silent.

Write full analysis ONLY for LOAD-BEARING stages. Fold SUPPORTING observations into the nearest load-bearing stage. For NOT APPLICABLE stages, write one sentence of why and move on. Thoroughness is depth on what matters, not length on what doesn't.

**Evidence per claim.** Every interpretive claim must be anchored to a specific word, phrase, line, or passage quoted directly in the response. A claim without an inline quote is not a claim.

**Length contract.** Per load-bearing stage: 150–400 words of prose. Quote the text directly at least once per stage. Final synthesis (Stage 11): 500–800 words. Do not pad.

**Running synthesis.** After every 3 stages, pause for a 2–3 sentence "What we know so far" checkpoint that threads the meaning forward. Do not wait for the final synthesis to start making connections.

**Falsifiability.** Any time you assert a non-obvious reading, state in one clause what would disconfirm it. "This reading would fail if..."

---

YOUR TASK: Perform a deep close reading of this {mode_label}, guided by the
computational findings above but going far beyond them. Proceed through the
following stages using the two-pass method above:

## STAGE 1: FIRST READING — WHAT DOES THE {mode_label.upper()} SAY?
Read the {mode_label} as a whole. What is it about on the surface? What is the
literal situation, scene, or argument? Who is speaking, to whom, and under what
circumstances? (Foster: take the surface with extreme seriousness.)

## STAGE 2: SOUND AND MUSIC
Read the {mode_label} aloud (or imagine doing so). What do you HEAR?
- What is the dominant rhythm? Is there a metrical pattern? (Ciardi: meaningful
  scansion vs. mechanical scansion — what does the rhythm FEEL like?)
- Where does the rhythm break or shift? What do those disruptions accomplish?
- What sounds dominate? (Pinsky: consonant braiding, vowel threading)
- Are there rhymes? What kind? (Hollander: full, slant, internal, absent?)
- How does the sound support, complicate, or contradict the meaning?

## STAGE 3: FORM AND STRUCTURE
What is the {mode_label}'s architecture?
- Is it a recognized form? (sonnet, villanelle, free verse, prose poem?)
- How are stanzas/sections organized? What do the divisions accomplish?
- Where is the VOLTA — the turn, the shift? (Hollander: the pivotal moment)
- How does the ending relate to the beginning? (Ciardi: circular, progressive,
  or irresolutive closure?)
- Are there refrains, anaphora, or repeated structures? What accumulates?

## STAGE 4: FIGURATIVE LANGUAGE
What comparisons does the {mode_label} make?
- Identify all similes and metaphors. What is tenor? What is vehicle?
- Are metaphors sustained (dominant) or scattered? (Ciardi's distinction)
- Does the {mode_label} use symbol? What objects/actions carry weight beyond
  their literal meaning? (Foster: symbols are open, allegory is closed)
- Is there a controlling metaphor that governs the whole {mode_label}?

## STAGE 5: DICTION AND VOCABULARY
What words has the poet chosen, and what do those choices reveal?
- Is the vocabulary concrete or abstract? Specific or general?
  (Ciardi: "orchis" vs. "flower")
- Anglo-Saxon or Latinate? (Foster: blunt/embodied vs. formal/learned)
- Are there shifts in register? (Pinsky: mixing sacred and profane)
- Any unusual words, neologisms, or archaic terms? Why?
- What are the key words? What do they connote beyond their denotation?

## STAGE 6: IMAGERY AND SENSATION
What do you SEE, HEAR, FEEL, TASTE, SMELL?
- Which sensory domains dominate? (Ciardi: total sensory suggestion)
- Do images cluster into patterns? What themes do these clusters suggest?
- Are there recurring images that function like musical motifs? (Foster)
- How concrete is the imagery? Does the {mode_label} stay grounded or float
  into abstraction?

## STAGE 7: SPEAKER, VOICE, AND TONE
Who is speaking? How do they feel about what they're saying?
- Is this the poet speaking directly, or an adopted persona?
  (Pinsky: distinguish poet from speaker)
- What is the emotional register? Elegiac? Celebratory? Ironic?
- Does the tone shift? Where, and what triggers the shift?
- Is there dramatic irony? (Foster: irony trumps everything)
- Who is being addressed? Does the address shift?

## STAGE 8: ALLUSION AND INTERTEXTUALITY
What other texts, myths, or cultural references does this {mode_label} invoke?
- Biblical allusions? Classical/mythological? Literary? (Foster)
- How do these allusions layer meaning? What conversation is the {mode_label}
  having with its predecessors?
- Are there archetypal patterns? (Foster: quest, communion, rebirth, descent)

## STAGE 9: WHAT THE {mode_label.upper()} DOES NOT SAY
Absence is evidence. Close reading earns its keep here. Work through:
- **Expected topics that are missing.** Given the subject, situation, and genre, what would a
  reader expect the {mode_label} to address that it avoids? Name two or three specific absences
  and quote any passages where the absence is felt as a gap rather than neutral omission.
  (Strauss: conspicuous silence as technique; Pinsky on Moore: "the deepest feeling always
  shows itself in silence.")
- **Grammatical and rhetorical ellipses.** Are there sentences that trail off, stanzas that
  end before their argument completes, questions left unanswered, addressees who never respond?
  What function does each ellipsis perform?
- **The counterfactual {mode_label}.** What would a different poet, writing on the same
  subject, have felt compelled to include? Name at least one such element the {mode_label}
  pointedly omits, and ask what that omission protects or concedes.
- **Texture of silence.** Distinguish conspicuous silence (the absence is underlined by
  the surrounding text) from mere selectivity (the absence is structural, not rhetorical).
  Only the former is evidence.

## STAGE 10: CONTRADICTION AND PARADOX
Tension is where meaning happens. Do not resolve paradoxes prematurely. Work through:
- **Surface contradictions.** Quote any two passages that pull in opposite directions —
  assertions, tones, images, or valuations that cannot both be true at the literal level.
  Per Pinsky on Shakespeare: "two distinct, division none" holds contradictory terms in
  a single thought. Which of this {mode_label}'s contradictions are of that kind?
- **Paradoxes held unresolved.** Distinguish a contradiction (which asks to be solved) from
  a paradox (which asks to be held). Which does the {mode_label} offer? A paradox held open
  is often the load-bearing structure of the poem's meaning.
- **Ironic inversions.** Per Foster: irony trumps everything. Is the surface statement
  undercut by its vehicle, context, tone, or placement? Quote the passage where the ironic
  gap is widest and state what the {mode_label} actually says beneath the surface.
- **The paraphrase test.** Could a prose paraphrase preserve any of these tensions, or do
  they live only in the {mode_label}'s particular form? Contradictions that survive paraphrase
  are thematic; those that die in paraphrase are formal, and those are the interesting ones.

## STAGE 11: HOW THE {mode_label.upper()} MEANS
Synthesize your observations. How does this {mode_label} mean?
- How do form, sound, imagery, diction, and structure work TOGETHER
  to create meaning that could not be paraphrased? (Ciardi: the poem's
  "performance" cannot be separated from its "content")
- What is the {mode_label} doing that prose could not do?
- What experience does the {mode_label} create for the reader?
- What is the relationship between what the {mode_label} says and how it
  says it? Do they reinforce or complicate each other?

## STAGE 12: EVALUATION AND RESPONSE
Finally:
- What makes this {mode_label} succeed or struggle as a work of art?
- What is most remarkable about its craft?
- What would be lost if any element were changed?
- What does this {mode_label} teach you about reading?

---

IMPORTANT NOTES:
- You are analyzing HOW the text means, not just WHAT it means (Ciardi).
- The computational findings are starting points, not conclusions.
- Sound, form, and structure are not ornaments — they ARE the meaning.
- Read generously: assume the writer is skilled until proven otherwise.
- Multiple valid readings can coexist. Embrace ambiguity (Pinsky).

The text follows below. Begin your analysis immediately, starting with your two-pass
survey (silently, in your head — then write up the load-bearing stages).
"""
        return prompt

    # ==================================================================
    # EXPORT
    # ==================================================================

    def export_report(self, filepath: str):
        """Export the full analysis as a Markdown report."""
        if not self.results:
            self.full_analysis()

        lines = []
        lines.append(f"# Literary Analysis: {self.title}")
        lines.append(f"**Mode: {self.mode}**")
        lines.append("")
        lines.append(f"**Composite Literary Score: {self.results['composite_literary_score']}**")
        lines.append(f"*{self.results['score_interpretation']}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        stats = self.results['text_statistics']
        lines.append("## Text Statistics")
        lines.append(f"- Words: {stats['total_words']:,}")
        lines.append(f"- Lines: {stats['total_lines']:,}")
        lines.append(f"- Sentences: {stats['total_sentences']:,}")
        lines.append(f"- Stanzas: {stats['total_stanzas']}")
        lines.append(f"- Paragraphs: {stats['total_paragraphs']}")
        lines.append("")

        # Domain headers
        domain_map = {
            'meter': 'I. Prosody & Sound', 'fixed_form': 'II. Form & Structure',
            'metaphor_simile': 'III. Figurative Language',
            'etymology_register': 'IV. Diction & Vocabulary',
            'archetype': 'V. Narrative & Intertextual',
            'dramatic_monologue': 'VI. Speaker & Performance',
            'contradiction': 'VII. Shared Methods',
        }

        for name, analysis in self.results['analyses'].items():
            if name in domain_map:
                lines.append(f"## {domain_map[name]}")
                lines.append("")

            lines.append(f"### {analysis.get('method', name)}")
            lines.append(f"**Score: {analysis.get('score', 0)}**")
            lines.append("")

            if 'precedent' in analysis:
                lines.append(f"*{analysis['precedent']}*")
                lines.append("")

            if 'interpretation' in analysis:
                lines.append(f"> {analysis['interpretation']}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # LLM Prompt
        lines.append("## LLM Close Reading Prompt")
        lines.append("")
        lines.append("```")
        lines.append(self.generate_llm_prompt())
        lines.append("```")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        return filepath


# ---------------------------------------------------------------------------
# CLI / DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("LITERARY ANALYZER — Demonstration")
    print("=" * 70)
    print()

    demo_poem = """
Whose woods these are I think I know.
His house is in the village though;
He will not see me stopping here
To watch his woods fill up with snow.

My little horse must think it queer
To stop without a farmhouse near
Between the woods and frozen lake
The darkest evening of the year.

He gives his harness bells a shake
To ask if there is some mistake.
The only other sound's the sweep
Of easy wind and downy flake.

The woods are lovely, dark and deep,
But I have promises to keep,
And miles to go before I sleep,
And miles to go before I sleep.
"""

    analyzer = LiteraryAnalyzer()
    analyzer.load_text_string(demo_poem, title="Stopping by Woods on a Snowy Evening (Frost)")
    analyzer.set_mode('poetry')

    results = analyzer.full_analysis()

    print(f"Title: {results['title']}")
    print(f"Mode: {results['mode']}")
    print(f"Composite Literary Score: {results['composite_literary_score']}")
    print(f"Interpretation: {results['score_interpretation']}")
    print()
    print("Individual Method Scores:")
    for name, analysis in results['analyses'].items():
        print(f"  {analysis.get('method', name):55s} → {analysis.get('score', 0)}")
    print()

    report_path = "/sessions/sweet-youthful-wright/mnt/scriptorium/demo_literary_report.md"
    analyzer.export_report(report_path)
    print(f"Report exported to: {report_path}")
    print("=" * 70)
