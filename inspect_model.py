import pickle
import pandas as pd
import numpy as np

def inspect_model():
    try:
        with open('model/recommendation_model.pkl', 'rb') as f:
            model = pickle.load(f)
        
        movies = model['movies']
        
        # Check if year is in the titles
        print("Checking if year is in titles:")
        print(movies['title'].head())
        
        # Check some titles with "(year)" at the end
        sample_title = movies['title'].iloc[0]
        print(f"\nSample title with year: '{sample_title}'")
        
        # Replicate normalization logic
        import re
        _YEAR_RE = re.compile(r"\s*\(\d{4}\)\s*$")
        _ARTICLE_RE = re.compile(r",\s*(the|a|an|le|la|les|el|il|das|der|die|det|den)\s*$", re.I)

        def _normalise(title: str) -> str:
            t = title.lower().strip()
            print(f"Original: '{t}'")
            t = _YEAR_RE.sub("", t) 
            print(f"After year removal: '{t}'")
            m = _ARTICLE_RE.search(t)
            if m:
                article = m.group(1)
                t = article + " " + t[:m.start()]
                print(f"After article moving: '{t}'")
            return t.strip()

        print(f"Normalized sample: '{_normalise(sample_title)}'")
        
        test_case = "War Machine"
        print(f"User searches for: '{test_case}'")
        norm_test = _normalise(test_case)
        print(f"Normalized search: '{norm_test}'")
        
        titles_lower = movies['title'].str.lower().tolist()
        titles_normalised = [_normalise(t) for t in movies['title'].tolist()]
        
        print("\nChecking matching logic:")
        print(f"Is '{test_case.lower()}' in titles_lower? {test_case.lower() in titles_lower}")
        print(f"Is '{norm_test}' in titles_normalised? {norm_test in titles_normalised}")

        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    inspect_model()
