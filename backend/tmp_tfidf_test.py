from ai.tfidf_matcher import init_tfidf_matcher
from dev_store import SEED_MEALS

try:
    init_tfidf_matcher(SEED_MEALS)
    print('TF-IDF init OK')
except Exception as e:
    import traceback
    print('TF-IDF init error:', e)
    traceback.print_exc()
